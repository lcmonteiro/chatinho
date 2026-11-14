"""
Workspace providers: what ``ChatSession(workspaces=…)`` is given.

:class:`GitWorktrees` is the one shipped: a git worktree per peer. What a
workspace *is* — ``Workspace``, ``WorkspaceView``, the operations — is a shared
part, in :mod:`chatinho.shared_parts.workspace`.

Standard library only: git is needed when a provider starts, never at import.
"""

from .git import GitWorktrees, MergeConflict

__all__ = ["GitWorktrees", "MergeConflict"]
