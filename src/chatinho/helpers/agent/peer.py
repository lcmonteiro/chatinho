"""
``AgentPeer``: a LangChain agent as a chat peer, with the chat itself as its tools.

The agent is made by a factory (:class:`~chatinho.helpers.agent.factory.AgentFactory`)
the peer is given; everything the chat does around it is here: one run per
question, ``ask_<peer>``/``run_<command>``/``ws_<operation>`` tools, memory from
``context()``, attachments and the link check. The connectors are subclasses
that only choose a factory and defaults::

    class BasicAgentConnector(AgentPeer):
        def __init__(self, name, model, tools=(), **options):
            super().__init__(name, model, BasicAgent(), tools, **options)

This is one of the library's two base classes, with ``WorkspaceView``, and for
the same reason: what a subclass reuses is the behaviour itself.

Needs ``pip install 'chatinho[langchain]'``.
"""

import asyncio
import logging
from typing import Any, Dict, FrozenSet, Iterable, List, Optional, Sequence, Tuple

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from ...endpoint import Endpoint
from ...hooks import Ask, Commands, Context, Invoke, Peers, Say, WorkspaceGrant
from ...hooks import HookAnswer, HookAsk, HookCommands, HookContext, HookInvoke, HookListen, HookPeers
from ...hooks import HookSay, HookWorkspace, NoWorkspaceProvider
from ...hooks import declares, name_of, require
from ...keys import KeyUnavailable, read_async
from ...message import LOCAL, Attachment, ChatMessage, Reply, ReplyStatus
from ...query import Query
from ...workspaces import Workspace, WorkspaceView
from ..memory import MEMORY, earlier, speaker
from .factory import AgentFactory
from .graph import compile_graph
from .tools import Shape, chat_tools, workspace_tools

logger = logging.getLogger(__name__)


class Interrupted(RuntimeError):
    """The agent stopped to wait for a human decision (``interrupt_on``) nothing in the chat can give."""


def chat_model(model: Any) -> Any:
    """
    What a factory is given: the model as is, or an Endpoint made a chat model.

    An Endpoint becomes ``ChatOpenAI`` whose key is a function reading the
    endpoint's key source when the model is called: never at creation, and
    never kept as text.
    """
    if not isinstance(model, Endpoint):
        return model
    from langchain_openai import ChatOpenAI
    source = model.key
    where  = "profile %r" % model.profile if model.profile else "the endpoint"

    async def api_key() -> str:
        if source is None:
            raise KeyUnavailable("%s has no API key configured" % where)
        return (await read_async(source)).reveal()

    return ChatOpenAI(model=model.model or "gpt-4o", base_url=model.base_url, api_key=api_key)


@require(HookAnswer)
@require(HookListen)
@require(HookSay)
@require(HookAsk)
@require(HookContext)
@require(HookPeers)
@require(HookCommands)
@require(HookInvoke)
@require(HookWorkspace)
class AgentPeer:
    """
    An agent that answers in the chat, with the chat as its tools.

    Args:
        name: Its name in the chat; also the agent's ``name`` unless one is given.
        model: What the factory takes (for LangChain, a model name such as
            ``"openai:gpt-4o"``, or a chat model), or an
            :class:`~chatinho.endpoint.Endpoint`.
        factory: What makes the agent: an
            :class:`~chatinho.helpers.agent.factory.AgentFactory`.
        tools: The agent's own tools. The chat's are added to them; on a clash
            of names the caller's tool wins.
        memory: Which earlier messages the agent is given, as a
            :class:`~chatinho.query.Query`; None for none.
        peers: Only these peers become ``ask_`` tools; None for every peer
            that answers.
        commands: Only these commands become ``run_`` tools; None for all.
        ask_user: Whether the agent gets ``ask_user``, which asks the user and
            waits for the answer.
        link_retries: How many times one run sends the model back for a file
            its answer does not link; 0 never does.
        workspace: Whether the agent works in its workspace: one
            ``ws_<operation>`` per operation of its own, and one
            ``ws_<operation>_of`` per operation that reads, less what the
            factory covers. They need a session given ``workspaces``; without
            one, the agent gets none and says so once.
        **options: Anything else the factory takes, passed through unchanged.

    Raises:
        TypeError: An option the factory does not take.
    """

    ask       : Ask
    say       : Say
    context   : Context
    peers     : Peers
    commands  : Commands
    invoke    : Invoke
    workspace : WorkspaceGrant

    def __init__(
        self,
        name         : str,
        model        : Any,
        factory      : AgentFactory,
        tools        : Sequence[Any] = (),
        *,
        memory       : Optional[Query] = MEMORY,
        peers        : Optional[Iterable[str]] = None,
        commands     : Optional[Iterable[str]] = None,
        ask_user     : bool = False,
        link_retries : int = 1,
        workspace    : bool = False,
        **options    : Any,
    ) -> None:
        unknown = sorted(set(options) - factory.options)
        if unknown:
            raise TypeError("%s does not take %s" % (factory.name, ", ".join(repr(u) for u in unknown)))
        self.name         = name
        self.model        = chat_model(model)
        self.factory      = factory
        self.tools        = list(tools)
        self.memory       = memory
        self.ask_user     = ask_user
        self.link_retries = link_retries
        #: Whether it works in its workspace. Not ``self.workspace``: that is the grant.
        self.uses_workspace = workspace
        #: Whether it already said it has no workspace provider, so it says it once.
        self._said_no_workspace = False
        #: The peers and commands that may become tools; None for all.
        self.allowed_peers    : Optional[FrozenSet[str]] = None if peers is None else frozenset(peers)
        self.allowed_commands : Optional[FrozenSet[str]] = None if commands is None else frozenset(commands)
        #: What the factory is given besides the model and the tools.
        self.options : Dict[str, Any] = {"name": name, **options}
        #: The compiled graph, and the shape of the chat it was built for.
        self._built  : Optional[Tuple[Shape, Any]] = None
        #: So two first questions at once build it once.
        self._building = asyncio.Lock()

    def __repr__(self) -> str:
        return "%s(name=%r)" % (type(self).__name__, self.name)

    # === Being asked, being told =====================================================

    async def answer(self, msg: ChatMessage) -> Reply:
        """Runs the graph on the conversation and the question, and answers with its result."""
        try:
            text, files = await self._run(msg)
        except Exception as exc:
            return Reply(self._failed(exc), status=ReplyStatus.ERROR)
        return Reply(text, tuple(files))

    async def listen(self, msg: ChatMessage) -> None:
        """
        Responds to what the user says to nobody in particular with a say; ignores everyone else.

        A say addressed to this agent, the router's choice included, is
        answered through ``answer``, so it is not also responded to here — or
        the agent would answer it twice — and one addressed to another peer is
        that peer's to answer.
        """
        if msg.to is not None or not msg.is_local:
            return
        try:
            text, files = await self._run(msg)
        except Exception as exc:
            text, files = self._failed(exc), []
        await self.say(text, reply_to=msg.id, attachments=files)

    async def _run(self, msg: ChatMessage) -> Tuple[str, List[Attachment]]:
        """One run of the graph on *msg*: the answer's text and the run's files."""
        graph  = await self.graph()
        config = ({"configurable": {"thread_id": str(msg.id)}}
                  if self.options.get("checkpointer") is not None else None)
        output = await graph.ainvoke({"question": msg}, config=config)
        if output.get("__interrupt__"):
            # The agent inside stopped for a decision; nothing in the chat resumes it.
            raise Interrupted("the run stopped for a decision")
        return output["text"], list(output["attachments"])

    def _failed(self, exc: Exception) -> str:
        if isinstance(exc, Interrupted):
            logger.warning("%s: the run was interrupted", self.name)
            return ("%s: the run was interrupted, waiting for a decision nobody in the chat can give"
                    % self.name)
        if isinstance(exc, KeyUnavailable):
            logger.warning("%s: no key (%s)", self.name, exc)
            return "%s: %s" % (self.name, exc)
        # Not its message: a model's error may echo the prompt.
        logger.warning("%s: the agent failed (%s)", self.name, type(exc).__name__)
        return "%s: could not answer (%s)" % (self.name, type(exc).__name__)

    # === The graph ==================================================================

    async def graph(self) -> Any:
        """The compiled graph for the chat as it is now, built or rebuilt as needed."""
        shape = self._shape() + (await self._workspaced(),)
        async with self._building:
            if self._built is None or self._built[0] != shape:
                mine  = await self.own_workspace()
                tools = self.tools + chat_tools(self, shape)
                if mine is not None:
                    tools += workspace_tools(self, mine, self.factory.covered)
                # The graph keeps the checkpoints; the agent inside it, run as
                # its subgraph, saves under the same thread.
                options = {k: v for k, v in self.options.items() if k != "checkpointer"}
                inner   = await self.factory.build(self.model, tools, options, self)
                self._built = (shape, compile_graph(inner, self._history, self.link_retries,
                                                    checkpointer=self.options.get("checkpointer"),
                                                    name=self.options.get("name")))
            return self._built[1]

    def _shape(self) -> Tuple[Tuple[Tuple[int, str], ...], Tuple[str, ...]]:
        """Which peers and commands become tools now, after the filters."""
        me    = getattr(self, "peer_id", None)
        peers = tuple(sorted(
            (at, name_of(who)) for at, who in self.peers().items()
            if at not in (me, LOCAL) and declares(who, HookAnswer)
            and (self.allowed_peers is None or name_of(who) in self.allowed_peers)))
        commands = tuple(sorted(
            name for name in self.commands()
            if self.allowed_commands is None or name in self.allowed_commands))
        return peers, commands

    # === Workspaces, for the graph and for factories ===================================

    async def own_workspace(self) -> Optional[Workspace]:
        """
        Its own workspace; None when it does not use one or the session has no provider.

        For factories as well as the peer: a missing provider is logged once,
        however many ask.
        """
        if not self.uses_workspace:
            return None
        try:
            return await self.workspace()
        except NoWorkspaceProvider:
            if not self._said_no_workspace:
                self._said_no_workspace = True
                logger.warning("%s: the session has no workspace provider, so it works without one",
                               self.name)
            return None

    async def others_workspaces(self) -> Dict[str, WorkspaceView]:
        """
        The other peers' workspaces it can read, by name; for factories.

        Only those that already exist: asked with ``create=False``, so this
        makes nobody a worktree.
        """
        return {name: await self.workspace(name, create=False) for name in await self._workspaced()}

    async def _workspaced(self) -> Tuple[str, ...]:
        """
        The other peers in the chat that have a workspace, asked without making one.

        Empty for a peer that does not use its workspace, which then never
        calls ``workspace()`` at all, and in a session with no provider.
        """
        if not self.uses_workspace:
            return ()
        me    = getattr(self, "peer_id", None)
        found : List[str] = []
        for at, who in sorted(self.peers().items()):
            if at in (me, LOCAL):
                continue
            try:
                await self.workspace(name_of(who), create=False)
            except NoWorkspaceProvider:
                return ()
            except (KeyError, ValueError):
                continue                 # none yet, or a name no workspace can have
            found.append(name_of(who))
        return tuple(found)

    # === Memory =====================================================================

    def _history(self, msg: ChatMessage) -> List[BaseMessage]:
        """What ``memory`` selects, without the agent's own tool asks, then the question."""
        history : List[BaseMessage] = []
        if self.memory is not None:
            me     = getattr(self, "peer_id", None)
            roster = self.peers()
            remembered = earlier(self.context, self.memory, msg)
            # What it asked through its tools, and the answers to that, are not
            # the conversation: they were the work of answering it.
            asked = {m.id for m in remembered if m.frm == me and m.to is not None and m.reply_to is None}
            parents = self._parents(remembered, me)
            for m in remembered:
                if m.id in asked or m.reply_to in asked:
                    continue
                if m.id in parents:
                    history.append(_turn(parents[m.id], me, roster))
                history.append(_turn(m, me, roster))
        history.append(HumanMessage(content=msg.text))
        return history

    def _parents(self, earlier: List[ChatMessage], me: Optional[int]) -> Dict[Any, ChatMessage]:
        """
        For each of its own messages whose parent ``memory`` left out, that parent.

        A say of the user it responded to went to everyone, so a query for what
        passed with it does not select it; the response alone would read as
        an answer to nothing.
        """
        have    = {m.id for m in earlier}
        wanted  = {m.reply_to: m.id for m in earlier
                   if m.frm == me and m.reply_to is not None and m.reply_to not in have}
        if not wanted:
            return {}
        return {wanted[m.id]: m for m in self.context(Query()) if m.id in wanted}


def _turn(m: ChatMessage, me: Optional[int], roster: Dict[int, Any]) -> BaseMessage:
    role, content = speaker(m, me, roster)
    return AIMessage(content=content) if role == "assistant" else HumanMessage(content=content)
