"""
A LangChain agent as a chat peer, with the chat itself as its tools.

:class:`BasicAgentConnector` takes what LangChain's ``create_agent`` takes and builds
the agent itself, adding the chat to its tools: one ``ask_<peer>`` per other
peer that answers, one ``run_<command>`` per command, and — with
``workspace=True`` — one ``ws_<operation>`` per operation of its workspace. Each
question it is asked is one run of the agent::

    lead = BasicAgentConnector("lead", Endpoint.load(), tools=[search_docs],
                               system_prompt="Plan the work and ask coder to write it.")

Its memory is the chat: earlier messages come from ``context()``, so the agent
needs no checkpointer. A peer it asks may ask it back; the session bounds how
deep that goes (``ChatSession(max_depth=...)``).

It is :class:`~chatinho.helpers.agent.peer.AgentPeer` with
:class:`~chatinho.helpers.agent.basic.BasicAgent` as its factory.

Needs ``pip install 'chatinho[langchain]'``.
"""

from typing import Any, Sequence

from ...helpers.agent import AgentPeer, BasicAgent
from ...hooks import connector


@connector("agent")
class BasicAgentConnector(AgentPeer):
    """
    A LangChain ``create_agent`` agent that answers in the chat, with the chat as its tools.

    Takes what :class:`~chatinho.helpers.agent.peer.AgentPeer` takes but the
    factory, and what ``create_agent`` takes besides the model and the tools
    (``system_prompt``, ``middleware``, ``response_format``, ``checkpointer``…).

    Raises:
        TypeError: An option ``create_agent`` does not take.
    """

    def __init__(self, name: str, model: Any, tools: Sequence[Any] = (), **options: Any) -> None:
        super().__init__(name, model, BasicAgent(), tools, **options)
