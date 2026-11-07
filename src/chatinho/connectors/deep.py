"""
A LangChain deep agent as a chat peer, working in its own workspace.

:class:`DeepAgentConnector` is :class:`~chatinho.connectors.agent.AgentConnector`
with ``create_deep_agent`` in place of ``create_agent``: the same chat around the
agent — ``ask_<peer>``, ``run_<command>``, memory from ``context()``,
attachments, a say for what the user says — and deep agents' planning,
subagents and file tools inside it. Its backend is its workspace::

    /                  its own workspace, read and written by its file tools
    /peers/<name>/     each other peer's workspace, read only

so ``read_file``, ``edit_file`` and ``grep`` work in its git worktree, and read
everyone else's. The ``ws_`` tools it gets are only what those cannot reach:
``ws_diff``, ``ws_log``, ``ws_commit``, their ``_of`` forms, and any operation a
project adds.

    dev = DeepAgentConnector("dev", Endpoint.load(), system_prompt="Fix what you are asked to.")
    build_chat_session(connectors=[dev], workspaces=GitWorktrees(".")).run()

Needs ``pip install 'chatinho[deepagents]'``.
"""

import inspect
import logging
from typing import Any, Dict, FrozenSet, List, Optional, Sequence

from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend
from deepagents.backends.protocol import BackendProtocol
from langchain_core.messages import SystemMessage

from ..hooks import NoWorkspaceProvider, connector
from ..workspaces.deepagents import WorkspaceBackend
from .agent import AgentConnector

logger = logging.getLogger(__name__)

#: Where the other peers' workspaces are, in the deep agent's file system.
PEERS = "/peers/"

#: What the agent is told first, so it knows whose files are where.
WHERE = ("Your files are your own git worktree, at '/': read, edit and write them with your file tools, "
         "and commit with ws_commit when a change is complete. The other peers' work is under "
         "'%s<name>/', which you can read and cannot change." % PEERS)

#: What ``create_deep_agent`` takes besides the model and the tools, less what the chat owns:
#: ``memory`` is the connector's own Query (deep agents' is ``agent_memory`` here), and the
#: workspace is the backend.
DEEP_OPTIONS : FrozenSet[str] = (
    frozenset(inspect.signature(create_deep_agent).parameters) - {"model", "tools", "memory", "backend"}
)


@connector("deep")
class DeepAgentConnector(AgentConnector):
    """
    A deep agent that answers in the chat, working in its own workspace.

    Takes what :class:`~chatinho.connectors.agent.AgentConnector` takes, and
    what ``create_deep_agent`` takes besides (``subagents``, ``skills``,
    ``permissions``, ``interrupt_on``, ``store``…), with two differences:

    Args:
        agent_memory: Deep agents' own ``memory`` — the ``AGENTS.md``-style
            sources it loads. ``memory`` stays the chat's: the Query of earlier
            messages the agent is given, as for ``AgentConnector``.
        workspace: Whether it works in its workspace; True by default, since
            that is what a deep agent is for here.

    Raises:
        TypeError: A ``backend`` — the workspace is the backend — or an option
            ``create_deep_agent`` does not take.
    """

    FACTORY = staticmethod(create_deep_agent)
    OPTIONS = DEEP_OPTIONS
    #: Deep agents' file tools reach these through the backend; a ws_ tool would be a second door.
    COVERED = frozenset({"ls", "read", "glob", "grep", "write", "edit", "delete"})

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
        super().__init__(name, model, tools, workspace=workspace, **options)
        self.agent_memory = agent_memory

    def __repr__(self) -> str:
        return "DeepAgentConnector(name=%r)" % self.name

    async def _factory_options(self) -> Dict[str, Any]:
        """Its memory sources, and — with a workspace provider — its backend and where things are."""
        extra : Dict[str, Any] = {}
        if self.agent_memory is not None:
            extra["memory"] = list(self.agent_memory)
        if not self.uses_workspace:
            return extra
        try:
            mine = await self.workspace()
        except NoWorkspaceProvider:
            if not self._said_no_workspace:
                self._said_no_workspace = True
                logger.warning("%s: the session has no workspace provider; deep agents' default backend "
                               "it is", self.name)
            return extra
        routes : Dict[str, BackendProtocol] = {}
        for name in await self._workspaced():
            routes["%s%s/" % (PEERS, name)] = WorkspaceBackend(await self.workspace(name, create=False))
        extra["backend"]       = CompositeBackend(default=WorkspaceBackend(mine), routes=routes)
        extra["system_prompt"] = _told(self.options.get("system_prompt"))
        return extra


def _told(given: Any) -> Any:
    """*given* system prompt, with where things are said first."""
    if given is None:
        return WHERE
    if isinstance(given, str):
        return WHERE + "\n\n" + given
    if isinstance(given, SystemMessage) and isinstance(given.content, str):
        return SystemMessage(content=WHERE + "\n\n" + given.content)
    logger.warning("A system prompt of type %s is kept as it is, without where the files are",
                   type(given).__name__)
    return given
