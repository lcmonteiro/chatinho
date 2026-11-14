"""
A workspace, and the view of it everyone but its owner gets.

``WorkspaceView`` holds what may be done to someone else's work: read it.
``Workspace`` subclasses it with what only its owner may do: change it. The
one-writer rule is that split, not a check — a view has no ``write`` to call,
so mypy refuses the call and so does Python.

The base class is deliberate, against the rest of the library, where peers
have none: here the operations *are* the behaviour inherited, and extending
the set is subclassing the layer an operation belongs to.
"""

import asyncio
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .operations import operation
from .tree import GIT_DIR, Tree

#: How much of one match's text grep returns before cutting it.
MATCH_TEXT_LIMIT : int = 500


@dataclass(frozen=True)
class Lines:
    """
    A window of a file's lines.

    Attributes:
        text: The lines, with their line endings.
        start: The 1-indexed number of the first line in the window.
        more: Whether lines remain after the window.
    """

    text  : str
    start : int
    more  : bool


@dataclass(frozen=True)
class Match:
    """
    One place a pattern matched.

    Attributes:
        path: The file, relative to the workspace's root.
        start: The line the match starts on, 1-indexed.
        end: The line it ends on; the same as *start* for a match on one line.
        text: The lines the match spans, cut past :data:`MATCH_TEXT_LIMIT`
            characters with a note saying so.
    """

    path  : str
    start : int
    end   : int
    text  : str


@dataclass(frozen=True)
class Matches:
    """
    What a search found.

    Attributes:
        matches: The matches, file by file, in order.
        truncated: Whether it stopped at its limit with more still to find.
    """

    matches   : Tuple[Match, ...]
    truncated : bool = False


def _cut(text: str) -> str:
    if len(text) <= MATCH_TEXT_LIMIT:
        return text
    return text[:MATCH_TEXT_LIMIT] + "… [cut: %d more characters]" % (len(text) - MATCH_TEXT_LIMIT)


def _search(tree: Tree, names: List[str], regex: "re.Pattern[str]", multiline: bool,
            limit: int) -> Matches:
    """The search itself, run in a thread: it reads files and it can be long."""
    found : List[Match] = []
    for name in names:
        try:
            text = (tree.root / name).read_bytes().decode("utf-8")
        except (OSError, UnicodeDecodeError):
            continue                         # gone since listed, or not text
        lines = text.splitlines(keepends=True)
        if multiline:
            for hit in regex.finditer(text):
                start = text.count("\n", 0, hit.start()) + 1
                end   = text.count("\n", 0, max(hit.start(), hit.end() - 1)) + 1
                found.append(Match(name, start, end, _cut("".join(lines[start - 1:end]))))
                if len(found) > limit:
                    return Matches(tuple(found[:limit]), truncated=True)
        else:
            for number, line in enumerate(lines, start=1):
                if regex.search(line.rstrip("\r\n")):
                    found.append(Match(name, number, number, _cut(line)))
                    if len(found) > limit:
                        return Matches(tuple(found[:limit]), truncated=True)
    return Matches(tuple(found))


class WorkspaceView:
    """
    Someone's workspace, read-only: what every peer but its owner gets.

    Each operation reads the working tree as it is now, uncommitted work
    included: a reviewer reads the work in progress, which is the point.

    Attributes:
        tree: The worktree underneath; operations reach files only through it.
    """

    def __init__(self, tree: Tree) -> None:
        self.tree : Tree = tree

    @property
    def name(self) -> str:
        """The name of the peer whose workspace it is."""
        return self.tree.owner

    def __repr__(self) -> str:
        return "%s(%r)" % (type(self).__name__, self.name)

    @operation("List a directory of the workspace; directories end with '/'")
    async def ls(self, path: str = ".") -> List[str]:
        """
        The entries of the directory at *path*, sorted, git's metadata left out.

        Raises:
            NotADirectoryError: When *path* is not a directory.
        """
        full = self.tree.resolve(path)

        def entries() -> List[str]:
            if not full.is_dir():
                raise NotADirectoryError("%r is not a directory" % path)
            return sorted(entry.name + ("/" if entry.is_dir() else "")
                          for entry in os.scandir(full) if entry.name != GIT_DIR)
        return await asyncio.to_thread(entries)

    @operation("Read a file of the workspace, a window of lines at a time")
    async def read(self, path: str, offset: int = 0, limit: int = 2000) -> Lines:
        """
        At most *limit* lines of the file at *path*, from line *offset* (0-indexed).

        A negative *offset* reads from the first line, and a *limit* of zero or
        less returns no lines rather than failing.

        Raises:
            FileNotFoundError: When there is no such file.
            UnicodeDecodeError: When the file is not UTF-8 text.
        """
        text   = (await self.tree.read_bytes(path)).decode("utf-8")
        lines  = text.splitlines(keepends=True)
        offset = max(offset, 0)
        if limit <= 0:
            return Lines("", offset + 1, offset < len(lines))
        window = lines[offset:offset + limit]
        return Lines("".join(window), offset + 1, offset + limit < len(lines))

    @operation("Find files of the workspace by a glob pattern (*, **, ?)")
    async def glob(self, pattern: str, path: str = ".") -> List[str]:
        """
        The files under *path* whose path relative to it matches *pattern*.

        A pattern without ``/`` matches a file's name at any depth. Files git
        ignores are left out, and directories are never returned.
        """
        return await self.tree.files(path, pattern)

    @operation("Search the workspace's files with a regular expression, optionally across lines")
    async def grep(
        self,
        pattern   : str,
        path      : str = ".",
        glob      : Optional[str] = None,
        multiline : bool = False,
        limit     : int = 100,
    ) -> Matches:
        """
        Where *pattern* matches in the files under *path*.

        Without *multiline*, it is searched line by line. With it, ``.`` matches
        a newline too, so one match may span lines.

        Args:
            pattern: A Python regular expression.
            path: Where to search, relative to the root.
            glob: Only the files matching it.
            multiline: Whether a match may span lines.
            limit: The most matches returned.

        Returns:
            Matches: Up to *limit*, and whether more were found.

        Raises:
            ValueError: When *pattern* is not a valid regular expression, or
                *limit* is less than one.
        """
        if limit < 1:
            raise ValueError("limit must be at least 1, got %d" % limit)
        flags = re.MULTILINE | (re.DOTALL if multiline else 0)
        try:
            regex = re.compile(pattern, flags)
        except re.error as exc:
            raise ValueError("Invalid pattern %r: %s" % (pattern, exc)) from exc
        names = await self.tree.files(path, glob)
        return await asyncio.to_thread(_search, self.tree, names, regex, multiline, limit)

    @operation("Show the workspace's work: the working tree against where its branch left the base")
    async def diff(self) -> str:
        """
        The diff of the working tree, uncommitted and new files included, against the merge base.

        It reads through an index of its own, so neither the owner's staging
        area nor anything else of the worktree is touched.
        """
        merge_base = (await self.tree.git("merge-base", self.tree.base, "HEAD")).strip()
        with tempfile.TemporaryDirectory(prefix="chatinho-index-") as scratch:
            index = os.path.join(scratch, "index")
            env   = {"GIT_INDEX_FILE": index}
            await self.tree.git("read-tree", "HEAD", env=env)
            await self.tree.git("add", "-A", env=env)
            return await self.tree.git("diff", "--cached", "--no-color", merge_base, env=env)

    @operation("List the workspace's commits that are not on the base, newest first")
    async def log(self) -> List[str]:
        """Each commit on the branch and not on the base, as its short id and subject."""
        out = await self.tree.git("log", "--format=%h %s", "%s..HEAD" % self.tree.base)
        return [line for line in out.splitlines() if line]


class Workspace(WorkspaceView):
    """
    One's own workspace: everything a view reads, and the means to change it.

    Every operation here writes, so each runs under the workspace's lock.
    """

    @operation("Write a file of the workspace, creating the folders it needs", writes=True)
    async def write(self, path: str, text: str) -> None:
        """Writes *text* to the file at *path*, replacing what it held."""
        await self.tree.write_bytes(path, text.encode("utf-8"))

    @operation("Replace exact text in a file of the workspace", writes=True)
    async def edit(self, path: str, old: str, new: str, replace_all: bool = False) -> int:
        """
        Replaces the exact text *old* with *new* in the file at *path*.

        Args:
            path: The file.
            old: The text to replace, exactly as it is in the file.
            new: What replaces it.
            replace_all: Replace every occurrence; otherwise *old* must be unique.

        Returns:
            int: How many times it was replaced.

        Raises:
            ValueError: When *old* is empty or the same as *new*, when it does
                not occur, or when it occurs more than once without
                *replace_all*. The file is left as it was.
        """
        if not old:
            raise ValueError("The text to replace is empty")
        if old == new:
            raise ValueError("The text to replace is the same as its replacement")
        text  = (await self.tree.read_bytes(path)).decode("utf-8")
        count = text.count(old)
        if count == 0:
            raise ValueError("The text to replace does not occur in %r" % path)
        if count > 1 and not replace_all:
            raise ValueError("The text to replace is not unique in %r: it occurs %d times" % (path, count))
        await self.tree.write_bytes(path, text.replace(old, new).encode("utf-8"))
        return count

    @operation("Delete a file, or a folder and everything in it, from the workspace", writes=True)
    async def delete(self, path: str) -> None:
        """
        Removes what is at *path*.

        Raises:
            FileNotFoundError: When nothing is there.
            ValueError: When *path* is the workspace's root.
        """
        full = self.tree.resolve(path)
        if full == self.tree.root:
            raise ValueError("The workspace's root cannot be deleted")
        if not full.exists() and not full.is_symlink():
            raise FileNotFoundError("No file %r in the workspace" % path)

        def remove() -> None:
            if full.is_dir() and not full.is_symlink():
                shutil.rmtree(full)
            else:
                full.unlink()
        await asyncio.to_thread(remove)

    @operation("Commit every change in the workspace on its own branch", writes=True)
    async def commit(self, message: str) -> str:
        """
        Commits everything changed in the working tree and returns the commit's id.

        Raises:
            ValueError: When there is nothing to commit; no empty commit is made.
        """
        await self.tree.git("add", "-A")
        staged = await self.tree.git("diff", "--cached", "--name-only")
        if not staged.strip():
            raise ValueError("Nothing to commit in %s's workspace" % self.name)
        author = {"GIT_AUTHOR_NAME": self.name, "GIT_AUTHOR_EMAIL": "%s@chatinho.invalid" % self.name}
        await self.tree.git("commit", "--quiet", "-m", message, env=author)
        return (await self.tree.git("rev-parse", "HEAD")).strip()
