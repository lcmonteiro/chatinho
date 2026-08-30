"""Connectors for chatinho.

A connector is a plain class that declares what it can do with
:func:`~chatinho.chat_hooks.require`; there is no base class to inherit.
"""

from .a2a import A2AConnector
from .openai import OpenAIConnector

__all__ = [
    "A2AConnector",
    "OpenAIConnector",
]
