"""Connectors for chatinho.

A connector is a plain class that declares what it can do with
:func:`~chatinho.hooks.require`; there is no base class to inherit.

Each one needs its own extra, so they are imported on first use (PEP 562):
asking for ``McpConnector`` must not need the OpenAI client, nor the other way
round.
"""

from typing import Any

#: name -> the module that defines it.
_WHERE = {
    "A2AConnector"    : "chatinho.connectors.a2a",
    "OpenAIConnector" : "chatinho.connectors.openai",
    "McpConnector"    : "chatinho.connectors.mcp",
}

__all__ = sorted(_WHERE)


def __getattr__(name: str) -> Any:
    """Imports a connector's module only when the connector is asked for."""
    if name not in _WHERE:
        raise AttributeError("module %r has no attribute %r" % (__name__, name))
    from importlib import import_module
    return getattr(import_module(_WHERE[name]), name)
