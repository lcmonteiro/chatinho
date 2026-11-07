"""
Workspaces as git worktrees: one per peer, on a branch of its own.

:class:`GitWorktrees` is what ``ChatSession(workspaces=…)`` is given. It is not
a peer: no id, in nobody's roster. It keeps each peer's worktree at
``<repo>/.chatinho/worktrees/<name>``, on branch ``peer/<name>``, started from
the base the repository had checked out when it started — and it never removes
one on its own, because a worktree holds work, not cache.
"""

import asyncio
import logging
import re
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Union

from ..hooks import HookProvision, require
from .operations import operations_of
from .tree import GitError, Tree, run_git
from .views import Workspace, WorkspaceView

logger = logging.getLogger(__name__)

#: Where the worktrees live, relative to the repository's top level.
WORKTREES = Path(".chatinho") / "worktrees"
#: The prefix of every workspace's branch.
BRANCH_PREFIX = "peer/"
#: A name that is safe as a directory and as a branch.
_NAME = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]*\Z")


class MergeConflict(RuntimeError):
    """A merge into the base conflicted; it was aborted and the base is as it was."""

    def __init__(self, name: str, paths: List[str]) -> None:
        super().__init__("Merging %s's workspace conflicts in %s; nothing was merged"
                         % (name, ", ".join(paths) or "unknown paths"))
        self.paths : List[str] = paths


@require(HookProvision)
class GitWorktrees:
    """
    Keeps each peer's workspace as a git worktree of one repository.

    Args:
        repo: The repository, or any directory inside it.
        base: The branch every workspace starts from and merges into; the one
            checked out when the provider starts, when None.
        view: The class other peers read a workspace through.
        workspace: The class an owner works in its own through; it must
            subclass *view*, so the owner can do everything a reader can.

    Raises:
        TypeError: When *workspace* does not subclass *view*, or *view* has an
            operation that writes.
    """

    name = "workspaces"

    def __init__(
        self,
        repo      : Union[str, Path],
        base      : Optional[str] = None,
        view      : type = WorkspaceView,
        workspace : type = Workspace,
    ) -> None:
        if not (isinstance(view, type) and issubclass(view, WorkspaceView)):
            raise TypeError("view must be a subclass of WorkspaceView, got %r" % (view,))
        if not (isinstance(workspace, type) and issubclass(workspace, view)):
            raise TypeError("The workspace class %s must subclass the view class %s, or an operation "
                            "added to the view is invisible to its owner"
                            % (getattr(workspace, "__name__", workspace), view.__name__))
        writing = [op.name for op in operations_of(view) if op.writes]
        if writing:
            raise TypeError("The view class %s declares writing operations (%s); a view only reads"
                            % (view.__name__, ", ".join(writing)))
        self.repo      : Path = Path(repo).expanduser()
        self.base      : Optional[str] = base
        self.view      : type = view
        self.workspace : type = workspace
        #: The repository's top level, once started.
        self._top      : Optional[Path] = None
        #: ``-c`` options naming a committer, when the repository configures none.
        self._identity : List[str] = []
        #: Each workspace opened so far, by name: one Tree, so one lock, per workspace.
        self._trees    : Dict[str, Tree] = {}
        #: So two first asks for one workspace create it once.
        self._opening  : asyncio.Lock = asyncio.Lock()

    def __repr__(self) -> str:
        return "GitWorktrees(%r, base=%r)" % (str(self.repo), self.base)

    # === Starting ===================================================================

    async def initialize(self) -> None:
        """
        Checks the repository and the base, and keeps the worktrees out of ``git status``.

        Raises:
            ValueError: When the directory is not in a git repository, or the
                base does not exist.
        """
        if self._top is not None:
            return
        if not self.repo.is_dir():
            raise ValueError("%s is not a directory" % self.repo)
        try:
            top = Path((await run_git(self.repo, "rev-parse", "--show-toplevel")).strip())
        except GitError as exc:
            raise ValueError("%s is not a git repository: %s" % (self.repo, exc)) from exc
        if self.base is None:
            branch = (await run_git(top, "symbolic-ref", "--quiet", "--short", "HEAD", check=False)).strip()
            self.base = branch or (await run_git(top, "rev-parse", "HEAD")).strip()
        else:
            try:
                await run_git(top, "rev-parse", "--verify", "--quiet", "%s^{commit}" % self.base)
            except GitError as exc:
                raise ValueError("The base %r does not exist in %s" % (self.base, top)) from exc
        for key, fallback in (("user.name", "chatinho"), ("user.email", "chatinho@chatinho.invalid")):
            if not (await run_git(top, "config", key, check=False)).strip():
                self._identity += ["-c", "%s=%s" % (key, fallback)]
        exclude = Path((await run_git(top, "rev-parse", "--git-path", "info/exclude")).strip())
        exclude = exclude if exclude.is_absolute() else top / exclude
        await asyncio.to_thread(_exclude, exclude, "/%s/" % WORKTREES.parts[0])
        self._top = top

    async def _started(self) -> Path:
        await self.initialize()
        assert self._top is not None
        return self._top

    # === The hook ===================================================================

    async def provision(self, owner: Optional[str], name: str, create: bool = True) -> WorkspaceView:
        """
        *name*'s workspace, writable when *owner* is *name*, a view otherwise.

        Args:
            owner: Who asks: a peer's name, or None for a command.
            name: Whose workspace.
            create: Whether to create it when it does not exist yet.

        Returns:
            WorkspaceView: A ``workspace`` instance for its owner, a ``view`` one for anyone else.

        Raises:
            KeyError: When it does not exist and *create* is False.
            ValueError: When *name* cannot be a directory and a branch.
        """
        tree = await self._tree(name, create)
        return (self.workspace if owner == name else self.view)(tree)

    async def _tree(self, name: str, create: bool) -> Tree:
        if not _NAME.match(name):
            raise ValueError("%r cannot name a workspace: use letters, digits, '_', '.' and '-'" % name)
        top = await self._started()
        async with self._opening:
            tree = self._trees.get(name)
            if tree is not None and tree.root.is_dir():
                return tree
            path   = top / WORKTREES / name
            branch = BRANCH_PREFIX + name
            exists = await self._branch_exists(branch)
            if not (path / ".git").exists():
                if exists:
                    await run_git(top, "worktree", "prune")
                    await run_git(top, "worktree", "add", "--quiet", str(path), branch)
                elif create:
                    await run_git(top, "worktree", "add", "--quiet", "-b", branch, str(path),
                                  self.base or "HEAD")
                    logger.info("Created %s's workspace at %s", name, path)
                else:
                    raise KeyError(name)
            tree = Tree(path, name, branch, self.base or "HEAD", self.view, self._identity)
            self._trees[name] = tree
            return tree

    async def _branch_exists(self, branch: str) -> bool:
        top = await self._started()
        out = await run_git(top, "rev-parse", "--verify", "--quiet", "refs/heads/" + branch, check=False)
        return bool(out.strip())

    # === What /ws does ==============================================================

    async def names(self) -> List[str]:
        """The workspaces that exist: every worktree on a ``peer/`` branch under the worktrees directory."""
        top    = await self._started()
        listed = await run_git(top, "worktree", "list", "--porcelain")
        found  : List[str] = []
        for line in listed.splitlines():
            if line.startswith("branch refs/heads/" + BRANCH_PREFIX):
                name = line[len("branch refs/heads/" + BRANCH_PREFIX):]
                if (top / WORKTREES / name).is_dir():
                    found.append(name)
        return sorted(found)

    async def ahead(self, name: str) -> int:
        """How many commits *name*'s branch has that the base has not."""
        top = await self._started()
        out = await run_git(top, "rev-list", "--count", "%s..%s" % (self.base, BRANCH_PREFIX + name))
        return int(out.strip() or 0)

    async def merge(self, name: str) -> str:
        """
        Merges *name*'s branch into the base, and leaves the workspace in place.

        The merge runs where the base is checked out — the repository itself,
        usually — or in a temporary worktree when it is checked out nowhere.

        Returns:
            str: What git said.

        Raises:
            KeyError: When there is no such workspace.
            MergeConflict: When it conflicts; the merge is aborted first.
        """
        if name not in await self.names():
            raise KeyError(name)
        top   = await self._started()
        where = await self._checked_out(self.base or "")
        if where is not None:
            return await self._merge_in(where, name)
        with tempfile.TemporaryDirectory(prefix="chatinho-merge-") as scratch:
            temporary = Path(scratch) / "base"
            await run_git(top, "worktree", "add", "--quiet", str(temporary), self.base or "HEAD")
            try:
                return await self._merge_in(temporary, name)
            finally:
                await run_git(top, "worktree", "remove", "--force", str(temporary), check=False)

    async def _merge_in(self, where: Path, name: str) -> str:
        try:
            return await run_git(where, *self._identity, "merge", "--no-edit", BRANCH_PREFIX + name)
        except GitError:
            conflicted = await run_git(where, "diff", "--name-only", "--diff-filter=U", check=False)
            await run_git(where, "merge", "--abort", check=False)
            raise MergeConflict(name, [p for p in conflicted.splitlines() if p])

    async def _checked_out(self, branch: str) -> Optional[Path]:
        """The worktree that has *branch* checked out, or None."""
        top     = await self._started()
        listed  = await run_git(top, "worktree", "list", "--porcelain")
        current : Optional[Path] = None
        for line in listed.splitlines():
            if line.startswith("worktree "):
                current = Path(line[len("worktree "):])
            elif line == "branch refs/heads/" + branch:
                return current
        return None

    async def drop(self, name: str) -> None:
        """
        Removes *name*'s worktree and deletes its branch, unmerged work and all.

        Raises:
            KeyError: When there is no such workspace.
        """
        if name not in await self.names():
            raise KeyError(name)
        top = await self._started()
        async with self._opening:
            await run_git(top, "worktree", "remove", "--force", str(top / WORKTREES / name))
            await run_git(top, "branch", "-D", BRANCH_PREFIX + name)
            self._trees.pop(name, None)


def _exclude(path: Path, pattern: str) -> None:
    """Adds *pattern* to the repository's own exclude file, once."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    if pattern not in lines:
        with path.open("a", encoding="utf-8") as out:
            out.write(("" if not lines or path.read_text(encoding="utf-8").endswith("\n") else "\n")
                      + pattern + "\n")
