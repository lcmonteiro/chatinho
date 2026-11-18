"""
Backends for chatinho.

A backend is a plain class that declares what it can do with
:func:`~chatinho.hooks.require`; there is no base class to inherit.
:class:`HiveBackend` needs only the standard library; :class:`DatabaseBackend`
needs ``chatinho[sql]`` and is imported on first use.
"""

from typing import TYPE_CHECKING, Any

from .hive import HiveBackend, HiveUnavailable

if TYPE_CHECKING:                       # never executed; read by type checkers
    from .database import DatabaseBackend

__all__ = [
    "DatabaseBackend",
    "HiveBackend",
    "HiveUnavailable",
]


# @req REQ-BACK-009
def __getattr__(name: str) -> Any:
    """Resolves ``DatabaseBackend`` on first use, so the hive's backend needs no SQLAlchemy (PEP 562)."""
    if name != "DatabaseBackend":
        raise AttributeError("module %r has no attribute %r" % (__name__, name))
    from .database import DatabaseBackend
    return DatabaseBackend
