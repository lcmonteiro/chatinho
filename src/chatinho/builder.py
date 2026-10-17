"""The two builders, by the name they have always had.

Each builder lives beside its frontend — :func:`build_chat_session` in
:mod:`chatinho.frontends.chat`, :func:`build_mcp_session` in
:mod:`chatinho.frontends.mcp` — so each needs only its own extra. This module
imports neither: reading a builder off it is resolved the way reading it off
``chatinho`` is, and a missing extra names itself there too.
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:                       # never executed; read by type checkers
    from .frontends.chat import build_chat_session
    from .frontends.mcp import build_mcp_session

__all__ = ["build_chat_session", "build_mcp_session"]


def __getattr__(name: str) -> Any:
    """Resolves a builder on first use, as :mod:`chatinho` does (PEP 562)."""
    if name not in __all__:
        raise AttributeError("module %r has no attribute %r" % (__name__, name))
    import chatinho
    return getattr(chatinho, name)
