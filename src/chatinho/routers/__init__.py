"""
Routers for chatinho.

A router decides who answers a say whose speaker named nobody, by declaring
:data:`~chatinho.hooks.HookRoute`. The session routes with whichever peer
declares it, and with :class:`SimpleRouter` when none does.
"""

from .simple import SimpleRouter

__all__ = [
    "SimpleRouter",
]
