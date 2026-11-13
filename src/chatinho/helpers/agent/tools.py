"""
The chat as an agent's tools: ``ask_<peer>``, ``run_<command>``, ``ask_user`` and ``ws_<operation>``.

Each builder takes the peer the tools work for, an
:class:`~chatinho.helpers.agent.peer.AgentPeer`, and uses its grants.
"""

import inspect
import logging
from typing import Any, Callable, Dict, FrozenSet, List, Optional, Tuple

from langchain_core.tools import StructuredTool
from pydantic import create_model

from ...message import LOCAL, Attachment, Reply, ReplyStatus
from ...workspaces import Operation, Workspace, operations_of
from .results import UNSAFE, diffed, shown

logger = logging.getLogger(__name__)

#: The shape of the chat an agent was built for: its peers (id, name), its commands,
#: and, for a peer that uses its workspace, the other peers that have one.
Shape = Tuple[Tuple[Tuple[int, str], ...], Tuple[str, ...], Tuple[str, ...]]


def tool_name(prefix: str, name: str) -> str:
    """*prefix* and *name* as a tool name the model APIs accept."""
    return (prefix + UNSAFE.sub("_", name))[:64]


def named(tool: Any) -> Optional[str]:
    """The name a caller's tool goes by: a tool's, a function's, or an OpenAI-style dict's."""
    if isinstance(tool, dict):
        return tool.get("name") or (tool.get("function") or {}).get("name")
    return getattr(tool, "name", None) or getattr(tool, "__name__", None)


def chat_tools(peer: Any, shape: Shape) -> List[StructuredTool]:
    """The chat as tools: ask_<peer>, run_<command> and, when wanted, ask_user."""
    theirs = {named(t) for t in peer.tools}
    taken  : set = set()
    found  : List[StructuredTool] = []

    def add(name: str, coroutine: Callable[..., Any], description: str) -> None:
        if name in theirs:
            logger.warning("%s: its own tool %r hides the chat's", peer.name, name)
            return
        unique, n = name, 2
        while unique in taken:
            unique, n = "%s_%d" % (name[:60], n), n + 1
        taken.add(unique)
        found.append(StructuredTool.from_function(coroutine=coroutine, name=unique,
                                                  description=description))

    peers, commands, _ = shape
    for at, name in peers:
        add(tool_name("ask_", name), _asking(peer, at, name),
            "Ask %s, another participant in this chat, and get its answer." % name)
    roster = peer.commands()
    for name in commands:
        described = getattr(roster.get(name), "description", "") or "Run the /%s command." % name
        add(tool_name("run_", name), _running(peer, name), described)
    if peer.ask_user:
        add("ask_user", _asking(peer, LOCAL, "the user"),
            "Ask the user a question and wait for the answer.")
    return found


def _asking(peer: Any, at: int, name: str) -> Callable[..., Any]:
    async def ask(question: str) -> Reply:
        try:
            return await peer.ask(at, question)
        except Exception as exc:
            # Only the type: an exception may echo a prompt.
            return Reply("%s failed: %s" % (name, type(exc).__name__), status=ReplyStatus.ERROR)
    return ask


def _running(peer: Any, name: str) -> Callable[..., Any]:
    async def run(arguments: str = "") -> str:
        try:
            answered = await peer.invoke(name, arguments)
        except Exception as exc:
            return "/%s failed: %s" % (name, type(exc).__name__)
        return answered if answered is not None else "(no answer)"
    return run


def workspace_tools(peer: Any, mine: Workspace, covered: FrozenSet[str]) -> List[StructuredTool]:
    """
    ``ws_<op>`` per operation of *mine*, ``ws_<op>_of`` per one that reads, less *covered*.

    Taken from the operations the provider's classes declare, so an operation a
    project adds becomes a tool here without a line of its own.
    """
    theirs = {named(t) for t in peer.tools}
    found  : List[StructuredTool] = []
    for op in operations_of(mine):
        if op.name not in covered:
            found.append(_operating(peer, op, None))
    for op in operations_of(mine.tree.view_class):
        if op.name not in covered:
            found.append(_operating(peer, op, "workspace"))
    kept = [t for t in found if t.name not in theirs]
    for hidden in sorted({t.name for t in found} - {t.name for t in kept}):
        logger.warning("%s: its own tool %r hides the workspace's", peer.name, hidden)
    return kept


def _operating(peer: Any, op: Operation, whose: Optional[str]) -> StructuredTool:
    """
    A tool running *op*: on the peer's own workspace, or, when *whose* names the
    argument that says which, on that peer's.
    """
    fields : Dict[str, Any] = {}
    if whose is not None:
        fields[whose] = (str, ...)
    for param in op.parameters:
        kind = Any if param.annotation is inspect.Parameter.empty else param.annotation
        fields[param.name] = (kind, ... if param.default is inspect.Parameter.empty else param.default)
    name   = tool_name("ws_", op.name + ("_of" if whose else ""))
    schema = create_model("%s_args" % name, **fields)

    async def run(**kwargs: Any) -> Tuple[str, Optional[Attachment]]:
        owner = kwargs.pop(whose) if whose else None
        try:
            target = await peer.workspace(owner)
            result = await getattr(target, op.name)(**kwargs)
        except Exception as exc:
            return "%s failed: %s: %s" % (name, type(exc).__name__, exc), None
        if op.name == "diff" and isinstance(result, str):
            return diffed(result, owner or peer.name)
        return shown(result), None

    described = op.description + ("; on another peer's workspace, which it only reads" if whose else "")
    return StructuredTool.from_function(coroutine=run, name=name, description=described,
                                        args_schema=schema, response_format="content_and_artifact")
