"""
``AgentFactory``: what makes the agent an :class:`~chatinho.helpers.agent.peer.AgentPeer` runs.

A factory is any object with these four members; there is nothing to subclass.
:class:`~chatinho.helpers.agent.basic.BasicAgent` and
:class:`~chatinho.helpers.agent.deep.DeepAgent` are the two shipped.
"""

from typing import Any, Dict, FrozenSet, List, Protocol


class AgentFactory(Protocol):
    """
    How one kind of agent is made.

    Attributes:
        name: What the factory is called in an error, as in "create_agent does
            not take 'x'".
        options: The keyword arguments it accepts besides the model and the
            tools; the peer refuses any other at creation.
        covered: The workspace operations the agent's own tools already reach;
            the peer gives it no ``ws_`` tool for them.
    """

    name    : str
    options : FrozenSet[str]
    covered : FrozenSet[str]

    async def build(self, model: Any, tools: List[Any], options: Dict[str, Any], peer: Any) -> Any:
        """
        The agent, made with the chat running.

        Called the first time the peer is asked anything and again whenever the
        chat's shape changes, never when the peer is created.

        Args:
            model: The chat model, an ``Endpoint`` already made one.
            tools: The peer's own tools, then the chat's.
            options: What the peer was given, ``name`` defaulting to the peer's
                and without ``checkpointer``, which the peer's own graph keeps.
            peer: The :class:`~chatinho.helpers.agent.peer.AgentPeer`, so the
                factory can await its grants.

        Returns:
            A runnable taking ``{"messages": [...]}`` and returning the
            messages, and a ``structured_response`` when it has one.
        """
        ...
