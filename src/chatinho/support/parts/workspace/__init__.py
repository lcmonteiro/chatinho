"""
What a workspace is, whoever provides it.

The pieces, from the bottom up:

- :class:`Tree` — one worktree's files and git, and the one door to a path;
- :func:`operation` / :func:`operations_of` — an operation is a declared method;
- :class:`WorkspaceView` / :class:`Workspace` — what a reader may do, and what
  the owner may do besides; extending is subclassing.

Standard library only. The provider that makes them is a specialization:
:class:`chatinho.workspaces.GitWorktrees`.
"""

from .operations import Operation, operation, operations_of
from .tree import GitError, Tree
from .views import Lines, Match, Matches, Workspace, WorkspaceView

__all__ = [
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
