"""
What the agent connectors share: ``AgentPeer`` and the factories that make its agent.

Needs ``chatinho[langchain]``. ``DeepAgent`` also needs ``chatinho[deepagents]``,
so it is imported on first use (PEP 562): importing ``AgentPeer`` or
``BasicAgent`` never imports deep agents.
"""

from typing import TYPE_CHECKING, Any

from .basic import BasicAgent
from .factory import AgentFactory
from .peer import AgentPeer, Interrupted

if TYPE_CHECKING:
    from .deep import DeepAgent

__all__ = ["AgentFactory", "AgentPeer", "BasicAgent", "DeepAgent", "Interrupted"]


def __getattr__(name: str) -> Any:
    """Imports ``DeepAgent`` only when it is asked for."""
    if name != "DeepAgent":
        raise AttributeError("module %r has no attribute %r" % (__name__, name))
    from .deep import DeepAgent
    return DeepAgent
