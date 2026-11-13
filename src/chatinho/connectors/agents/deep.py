"""
A LangChain deep agent as a chat peer, working in its own workspace.

:class:`DeepAgentConnector` is :class:`~chatinho.helpers.agent.peer.AgentPeer`
with :class:`~chatinho.helpers.agent.deep.DeepAgent` as its factory: the same
chat around the agent as the basic connector — ``ask_<peer>``, ``run_<command>``,
memory from ``context()``, attachments, a say for what the user says — and deep
agents' planning, subagents and file tools inside it. Its backend is its
workspace: ``/`` its own, ``/peers/<name>/`` everyone else's, read only.

    dev = DeepAgentConnector("dev", Endpoint.load(), system_prompt="Fix what you are asked to.")
    build_chat_session(connectors=[dev], workspaces=GitWorktrees(".")).run()

Needs ``pip install 'chatinho[deepagents]'``.
"""

from typing import Any, List, Optional, Sequence

from ...helpers.agent.deep import DeepAgent
from ...helpers.agent.peer import AgentPeer
from ...hooks import connector


@connector("deep")
class DeepAgentConnector(AgentPeer):
    """
    A deep agent that answers in the chat, working in its own workspace.

    Takes what :class:`~chatinho.helpers.agent.peer.AgentPeer` takes but the
    factory, and what ``create_deep_agent`` takes besides (``subagents``,
    ``skills``, ``permissions``, ``interrupt_on``, ``store``…), with two
    differences:

    Args:
        agent_memory: Deep agents' own ``memory`` — the ``AGENTS.md``-style
            sources it loads. ``memory`` stays the chat's: the Query of earlier
            messages the agent is given.
        workspace: Whether it works in its workspace; True by default, since
            that is what a deep agent is for here.

    Raises:
        TypeError: A ``backend`` — the workspace is the backend — or an option
            ``create_deep_agent`` does not take.
    """

    def __init__(
        self,
        name         : str,
        model        : Any,
        tools        : Sequence[Any] = (),
        *,
        workspace    : bool = True,
        agent_memory : Optional[List[str]] = None,
        **options    : Any,
    ) -> None:
        if "backend" in options:
            raise TypeError("DeepAgentConnector takes no backend: its workspace is its backend")
        super().__init__(name, model, DeepAgent(agent_memory), tools, workspace=workspace, **options)

    @property
    def agent_memory(self) -> Optional[List[str]]:
        """Deep agents' own memory sources, as its factory was given them."""
        return getattr(self.factory, "agent_memory", None)
