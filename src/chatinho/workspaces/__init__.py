"""
Somewhere for a peer to work: its own git worktree, which everyone else can read.

The pieces, from the bottom up:

- :class:`Tree` — one worktree's files and git, and the one door to a path;
- :func:`operation` / :func:`operations_of` — an operation is a declared method;
- :class:`WorkspaceView` / :class:`Workspace` — what a reader may do, and what
  the owner may do besides; extending is subclassing;
- :class:`GitWorktrees` — the provider ``ChatSession(workspaces=…)`` is given.

Standard library only: git is needed when a provider starts, never at import.
"""

from .git import GitWorktrees, MergeConflict
from .operations import Operation, operation, operations_of
from .tree import GitError, Tree
from .views import Lines, Match, Matches, Workspace, WorkspaceView

__all__ = [
    "GitWorktrees",
    "MergeConflict",
    "Operation",
    "operation",
    "operations_of",
    "GitError",
    "Tree",
    "Lines",
    "Match",
    "Matches",
    "Workspace",
    "WorkspaceView",
]
