"""Commands for chatinho.

A command is a plain class that declares what it can do with
:func:`~chatinho.chat_hooks.require`; there is no base class to inherit.
"""

from .help import HelpCommand
from .test import TestCommand

__all__ = [
    "HelpCommand",
    "TestCommand",
]
