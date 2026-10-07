"""Frontends for chatinho, beyond the terminal that ``build_chat`` builds.

A frontend is peer zero: it speaks for whoever is on the other side of the
chat. Each one needs its own extra, so they are imported on first use.
"""

from typing import Any

#: name -> the module that defines it.
_WHERE = {
    "McpFrontend" : "chatinho.frontends.mcp",
}

__all__ = sorted(_WHERE)


def __getattr__(name: str) -> Any:
    """Imports a frontend's module only when the frontend is asked for."""
    if name not in _WHERE:
        raise AttributeError("module %r has no attribute %r" % (__name__, name))
    from importlib import import_module
    return getattr(import_module(_WHERE[name]), name)
