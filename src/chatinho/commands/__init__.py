"""Commands for chatinho.

A command is a plain class that declares what it can do with
:func:`~chatinho.chat_hooks.require`; there is no base class to inherit.
"""

from .copy import CopyCommand
from .help import HelpCommand
from .test import TestCommand

__all__ = [
    "CopyCommand",
    "HelpCommand",
    "TestCommand",
]
