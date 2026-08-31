"""Backends for chatinho.

A backend is a plain class that declares what it can do with
:func:`~chatinho.chat_hooks.require`; there is no base class to inherit.
"""

from .database import DatabaseBackend

__all__ = [
    "DatabaseBackend",
]
