"""
``DeepAgent``: an agent made with LangChain's ``create_deep_agent``, working in its workspace.

Its backend is the peer's workspace::

    /                  its own workspace, read and written by its file tools
    /peers/<name>/     each other peer's workspace, read only

so ``read_file``, ``edit_file`` and ``grep`` work in its git worktree, and read
everyone else's. It covers the workspace operations those reach, so the peer
gives it only ``ws_diff``, ``ws_log``, ``ws_commit``, their ``_of`` forms, and
any operation a project adds.

Needs ``pip install 'chatinho[deepagents]'``.
"""

import inspect
import logging
from typing import Any, Dict, FrozenSet, List, Optional

from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend
from deepagents.backends.protocol import BackendProtocol
from langchain_core.messages import SystemMessage

from ...workspaces.deepagents import WorkspaceBackend

logger = logging.getLogger(__name__)

#: Where the other peers' workspaces are, in the deep agent's file system.
PEERS = "/peers/"

#: What the agent is told first, so it knows whose files are where.
WHERE = ("Your files are your own git worktree, at '/': read, edit and write them with your file tools, "
         "and commit with ws_commit when a change is complete. The other peers' work is under "
         "'%s<name>/', which you can read and cannot change." % PEERS)


class DeepAgent:
    """
    Makes the agent with ``create_deep_agent``, its workspace as its backend.

    It accepts what ``create_deep_agent`` takes besides the model and the tools,
    less what the chat owns: ``memory`` is the peer's own Query, so deep agents'
    is given here as *agent_memory*, and the workspace is the backend.

    Args:
        agent_memory: Deep agents' own ``memory``: the ``AGENTS.md``-style
            sources it loads.
    """

    name    : str            = "create_deep_agent"
    options : FrozenSet[str] = (frozenset(inspect.signature(create_deep_agent).parameters)
                                - {"model", "tools", "memory", "backend"})
    #: Deep agents' file tools reach these through the backend; a ws_ tool would be a second door.
    covered : FrozenSet[str] = frozenset({"ls", "read", "glob", "grep", "write", "edit", "delete"})

    def __init__(self, agent_memory: Optional[List[str]] = None) -> None:
        self.agent_memory = agent_memory

    def __repr__(self) -> str:
        return "DeepAgent(agent_memory=%r)" % (self.agent_memory,)

    async def build(self, model: Any, tools: List[Any], options: Dict[str, Any], peer: Any) -> Any:
        """
        ``create_deep_agent`` with its memory sources and, with a workspace, its backend and prompt.

        Without a workspace (the peer does not use one, or the session has no
        provider) it runs on deep agents' own default backend, and is not told
        about ``/peers/``.
        """
        options = dict(options)
        if self.agent_memory is not None:
            options["memory"] = list(self.agent_memory)
        mine = await peer.own_workspace()
        if mine is not None:
            routes : Dict[str, BackendProtocol] = {
                "%s%s/" % (PEERS, name): WorkspaceBackend(view)
                for name, view in (await peer.others_workspaces()).items()}
            options["backend"]       = CompositeBackend(default=WorkspaceBackend(mine), routes=routes)
            options["system_prompt"] = _told(options.get("system_prompt"))
        return create_deep_agent(model, tools=tools, **options)


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
