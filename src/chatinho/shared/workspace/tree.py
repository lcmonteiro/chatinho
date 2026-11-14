"""
The files and the git underneath one workspace.

Every operation reaches the worktree through a :class:`Tree`, never by
``open()`` or ``subprocess`` of its own: :meth:`Tree.resolve` is the one door
to a path, and it refuses anything outside the root, so an operation a project
writes cannot escape by forgetting to check. Python cannot make it the *only*
door — an operation may still call ``open()`` — which is the same honest limit
the session's own grants have.

Nothing here blocks the loop. Git runs as a subprocess the loop awaits, and
file work goes to a thread.
"""

import asyncio
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

#: A worktree's own git metadata: neither listed nor reachable through a path.
GIT_DIR = ".git"


class GitError(RuntimeError):
    """A git command failed; the message is what git said."""


def glob_regex(pattern: str) -> "re.Pattern[str]":
    """
    Compiles a glob into a regex over ``/``-separated relative paths.

    ``*`` and ``?`` stay inside one path segment, ``**`` spans segments, and
    ``[...]`` is a character class. A pattern with no ``/`` matches a file's
    name at any depth; a leading ``/`` anchors it to the search root.

    Args:
        pattern: The glob.

    Returns:
        re.Pattern: Matches a whole relative path.
    """
    anchored = pattern.startswith("/")
    body     = pattern.lstrip("/")
    out : List[str] = []
    i = 0
    while i < len(body):
        c = body[i]
        if body.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif body.startswith("**", i):
            out.append(".*")
            i += 2
        elif c == "*":
            out.append("[^/]*")
            i += 1
        elif c == "?":
            out.append("[^/]")
            i += 1
        elif c == "[":
            end = body.find("]", i + 1)
            if end == -1:
                out.append(re.escape(c))
                i += 1
            else:
                inner = body[i + 1:end]
                if inner.startswith("!"):
                    inner = "^" + inner[1:]
                out.append("[%s]" % inner)
                i = end + 1
        else:
            out.append(re.escape(c))
            i += 1
    regex = "".join(out)
    if "/" not in body and not anchored:
        regex = "(?:.*/)?" + regex
    return re.compile(regex + r"\Z")


class Tree:
    """
    One workspace's worktree: its root, its branch, its base, and its lock.

    Attributes:
        root: The worktree's directory.
        owner: The name of the peer whose workspace it is.
        branch: The branch the worktree has checked out.
        base: The branch, or commit, the workspace started from.
        view_class: The class other peers read this workspace through.
        lock: Held by every writing operation, so writes run one at a time.
    """

    def __init__(
        self,
        root       : Path,
        owner      : str,
        branch     : str,
        base       : str,
        view_class : type,
        identity   : Sequence[str] = (),
    ) -> None:
        self.root       : Path = Path(root).resolve()
        self.owner      : str = owner
        self.branch     : str = branch
        self.base       : str = base
        self.view_class : type = view_class
        self.lock       : asyncio.Lock = asyncio.Lock()
        #: ``-c`` options naming a committer when the repository has none configured.
        self._identity  : List[str] = list(identity)

    def __repr__(self) -> str:
        return "Tree(%r, branch=%r)" % (str(self.root), self.branch)

    # === Paths ======================================================================

    def resolve(self, path: str) -> Path:
        """
        The absolute path of *path*, relative to the root, refusing any way out.

        Args:
            path: Relative to the workspace's root; ``"."`` is the root itself.

        Returns:
            Path: Inside the root, symbolic links followed.

        Raises:
            ValueError: When *path* is absolute, leaves the root through ``..``
                or a symbolic link, or reaches into git's own metadata.
        """
        if os.path.isabs(path):
            raise ValueError("%r is absolute; paths are relative to the workspace" % path)
        full = (self.root / path).resolve()
        if full != self.root and self.root not in full.parents:
            raise ValueError("%r is outside the workspace" % path)
        relative = full.relative_to(self.root).parts
        if relative[:1] == (GIT_DIR,):
            raise ValueError("%r is git's own metadata" % path)
        return full

    def relative(self, full: Path) -> str:
        """*full* as a ``/``-separated path relative to the root."""
        return full.relative_to(self.root).as_posix()

    # === Git ========================================================================

    async def git(self, *args: str, env: Optional[Dict[str, str]] = None, check: bool = True,
                  cwd: Optional[Path] = None) -> str:
        """
        Runs git in the worktree and returns what it printed.

        Args:
            *args: git's arguments.
            env: Variables added to the environment for this run.
            check: Raise when git fails; when False, its output is returned anyway.
            cwd: Where to run it; the root when None.

        Returns:
            str: Its standard output.

        Raises:
            GitError: When git exits with an error and *check* is set.
        """
        return await run_git(cwd or self.root, *self._identity, *args, env=env, check=check)

    async def files(self, path: str = ".", glob: Optional[str] = None) -> List[str]:
        """
        The files under *path* git tracks or would track, relative to the root.

        New files are included and ignored ones left out, as
        ``git ls-files --cached --others --exclude-standard`` lists them; a
        tracked file deleted from the working tree is left out.

        Args:
            path: Where to look, relative to the root.
            glob: Only the files whose path relative to *path* matches it.

        Returns:
            List[str]: Sorted, ``/``-separated.
        """
        where  = self.resolve(path)
        listed = await self.git("ls-files", "--cached", "--others", "--exclude-standard", "-z",
                                "--", str(where))
        names  = sorted({name for name in listed.split("\0") if name})
        if glob is not None:
            matcher = glob_regex(glob)
            prefix  = self.relative(where)
            names   = [n for n in names
                       if matcher.match(n if prefix == "." else n[len(prefix) + 1:])]
        return await asyncio.to_thread(lambda: [n for n in names if (self.root / n).is_file()])

    # === Bytes ======================================================================

    async def read_bytes(self, path: str) -> bytes:
        """The contents of the file at *path*. Raises FileNotFoundError naming it."""
        full = self.resolve(path)
        if not full.is_file():
            raise FileNotFoundError("No file %r in the workspace" % path)
        return await asyncio.to_thread(full.read_bytes)

    async def write_bytes(self, path: str, data: bytes) -> None:
        """Writes *data* to *path*, creating the directories it needs."""
        full = self.resolve(path)
        if full == self.root or full.is_dir():
            raise IsADirectoryError("%r is a directory" % path)

        def write() -> None:
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_bytes(data)
        await asyncio.to_thread(write)


async def run_git(cwd: Path, *args: str, env: Optional[Dict[str, str]] = None, check: bool = True) -> str:
    """
    Runs ``git *args`` in *cwd* without blocking the loop.

    Args:
        cwd: The directory to run it in.
        *args: git's arguments.
        env: Variables added to the environment for this run.
        check: Raise when git fails.

    Returns:
        str: Its standard output.

    Raises:
        GitError: When git exits with an error and *check* is set, or is not installed.
    """
    environment : Dict[str, Any] = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    if env:
        environment.update(env)
    try:
        process = await asyncio.create_subprocess_exec(
            "git", *args, cwd=str(cwd), env=environment,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        raise GitError("git is not installed") from exc
    out, err = await process.communicate()
    if check and process.returncode != 0:
        raise GitError(err.decode("utf-8", "replace").strip() or "git %s failed" % " ".join(args))
    return out.decode("utf-8", "replace")
