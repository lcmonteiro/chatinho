"""
Commands for chatinho.

A command is a plain class that declares what it can do with
:func:`~chatinho.hooks.require`; there is no base class to inherit.
"""

from .help import HelpCommand
from .test import TestCommand
from .workspace import WorkspaceCommand

__all__ = [
    "HelpCommand",
    "TestCommand",
    "WorkspaceCommand",
]
