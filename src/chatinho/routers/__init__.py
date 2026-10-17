"""
Routers for chatinho.

A router decides who answers a say whose speaker named nobody, by declaring
:data:`~chatinho.hooks.HookRoute`. A session routes with the one it is given
as ``router=``; the builders give :class:`SimpleRouter`.
"""

from .simple import SimpleRouter

__all__ = [
    "SimpleRouter",
]
