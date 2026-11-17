"""
Routers for chatinho.

A router decides who answers a say whose speaker named nobody, by declaring
:data:`~chatinho.hooks.HookRoute`. A session routes with the one it is given
as ``router=``; the builders give :class:`SimpleRouter`.
"""

from typing import TYPE_CHECKING, Any

from .simple import SimpleRouter

if TYPE_CHECKING:                       # never executed; read by type checkers
    from .llm import LLMRouter

__all__ = [
    "LLMRouter",
    "SimpleRouter",
]


# @req REQ-ROUTE-011
def __getattr__(name: str) -> Any:
    """Resolves ``LLMRouter`` on first use, so importing the routers needs no ``openai`` (PEP 562)."""
    if name != "LLMRouter":
        raise AttributeError("module %r has no attribute %r" % (__name__, name))
    try:
        from .llm import LLMRouter
    except ImportError as exc:
        raise ImportError("LLMRouter needs chatinho[openai] (pip install 'chatinho[openai]'): %s"
                          % exc) from exc
    return LLMRouter
