"""A LangChain agent as a chat peer, with the chat itself as its tools.

:class:`AgentConnector` takes what LangChain's ``create_agent`` takes and builds
the agent itself, adding the chat to its tools: one ``ask_<peer>`` per other
peer that answers, one ``run_<command>`` per command. Each question it is asked
is one run of the agent::

    lead = AgentConnector("lead", Endpoint.load(), tools=[search_docs],
                          system_prompt="Plan the work and ask coder to write it.")

Its memory is the chat: earlier messages come from ``context()``, so the agent
needs no checkpointer. A peer it asks may ask it back; the session bounds how
deep that goes (``ChatSession(max_depth=...)``).

Needs ``pip install 'chatinho[langchain]'``.
"""

import asyncio
import inspect
import json
import logging
import re
from typing import Any, Callable, Dict, FrozenSet, Iterable, List, Optional, Sequence, Tuple

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.tools import StructuredTool

from ..endpoint import Endpoint
from ..hooks import Ask, Commands, Context, Invoke, Peers
from ..hooks import HookAnswer, HookAsk, HookCommands, HookContext, HookInvoke, HookPeers
from ..hooks import connector, declares, name_of, require
from ..keys import KeyUnavailable, read_async
from ..message import LOCAL, ChatMessage, Reply, ReplyStatus
from ..query import SELF, Query

logger = logging.getLogger(__name__)

#: What the agent remembers by default, as for the OpenAI connector: what passed
#: between it and anyone, without the replies that failed, the last twenty.
MEMORY = Query(peer=SELF, errors=False).last(20)

#: What ``create_agent`` takes besides the model and the tools.
OPTIONS : FrozenSet[str] = frozenset(inspect.signature(create_agent).parameters) - {"model", "tools"}

#: What a tool name may hold, for the OpenAI-compatible APIs.
_UNSAFE = re.compile(r"[^A-Za-z0-9_-]")

#: The shape of the chat the agent was built for: its peers (id, name) and commands.
Shape = Tuple[Tuple[Tuple[int, str], ...], Tuple[str, ...]]


def _tool_name(prefix: str, name: str) -> str:
    return (prefix + _UNSAFE.sub("_", name))[:64]


def _named(tool: Any) -> Optional[str]:
    """The name a caller's tool goes by: a tool's, a function's, or an OpenAI-style dict's."""
    if isinstance(tool, dict):
        return tool.get("name") or (tool.get("function") or {}).get("name")
    return getattr(tool, "name", None) or getattr(tool, "__name__", None)


def chat_model(model: Any) -> Any:
    """What ``create_agent`` is given: the model as is, or an Endpoint made a chat model.

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


@connector("agent")
@require(HookAnswer)
@require(HookAsk)
@require(HookContext)
@require(HookPeers)
@require(HookCommands)
@require(HookInvoke)
class AgentConnector:
    """A LangChain agent that answers in the chat, with the chat as its tools.

    Args:
        name: Its name in the chat; also the agent's ``name`` unless one is given.
        model: What ``create_agent`` takes (a model name such as
            ``"openai:gpt-4o"``, or a chat model), or an
            :class:`~chatinho.endpoint.Endpoint`.
        tools: The agent's own tools. The chat's are added to them; on a clash
            of names the caller's tool wins.
        memory: Which earlier messages the agent is given, as a
            :class:`~chatinho.query.Query`; None for none.
        peers: Only these peers become ``ask_`` tools; None for every peer
            that answers.
        commands: Only these commands become ``run_`` tools; None for all.
        ask_user: Whether the agent gets ``ask_user``, which asks the user and
            waits for the answer.
        **agent_options: Anything else ``create_agent`` takes
            (``system_prompt``, ``middleware``, ``response_format``,
            ``checkpointer``, ...), passed through unchanged.

    Raises:
        TypeError: An option ``create_agent`` does not take.
    """

    ask      : Ask
    context  : Context
    peers    : Peers
    commands : Commands
    invoke   : Invoke

    def __init__(
        self,
        name     : str,
        model    : Any,
        tools    : Sequence[Any] = (),
        *,
        memory   : Optional[Query] = MEMORY,
        peers    : Optional[Iterable[str]] = None,
        commands : Optional[Iterable[str]] = None,
        ask_user : bool = False,
        **agent_options: Any,
    ) -> None:
        unknown = sorted(set(agent_options) - OPTIONS)
        if unknown:
            raise TypeError("create_agent does not take %s" % ", ".join(repr(u) for u in unknown))
        self.name     = name
        self.model    = chat_model(model)
        self.tools    = list(tools)
        self.memory   = memory
        self.ask_user = ask_user
        #: The peers and commands that may become tools; None for all.
        self.allowed_peers    : Optional[FrozenSet[str]] = None if peers is None else frozenset(peers)
        self.allowed_commands : Optional[FrozenSet[str]] = None if commands is None else frozenset(commands)
        #: What is passed to create_agent besides the model and the tools.
        self.options : Dict[str, Any] = {"name": name, **agent_options}
        #: The compiled agent, and the shape of the chat it was built for.
        self._built  : Optional[Tuple[Shape, Any]] = None
        #: So two first questions at once build it once.
        self._building = asyncio.Lock()

    def __repr__(self) -> str:
        return "AgentConnector(name=%r)" % self.name

    # === Being asked ================================================================

    async def answer(self, msg: ChatMessage) -> Reply:
        """Runs the agent once on the conversation and the question, and answers with its result."""
        try:
            agent  = await self._agent()
            config = ({"configurable": {"thread_id": str(msg.id)}}
                      if self.options.get("checkpointer") is not None else None)
            state  = await agent.ainvoke({"messages": self._history(msg)}, config=config)
        except KeyUnavailable as exc:
            logger.warning("%s: no key (%s)", self.name, exc)
            return Reply("%s: %s" % (self.name, exc), status=ReplyStatus.ERROR)
        except Exception as exc:
            # Not its message: a model's error may echo the prompt.
            logger.warning("%s: the agent failed (%s)", self.name, type(exc).__name__)
            return Reply("%s: could not answer (%s)" % (self.name, type(exc).__name__),
                         status=ReplyStatus.ERROR)
        return Reply(_result(state))

    # === The agent ==================================================================

    async def _agent(self) -> Any:
        """The compiled agent for the chat as it is now, built or rebuilt as needed."""
        shape = self._shape()
        async with self._building:
            if self._built is None or self._built[0] != shape:
                tools = self.tools + self._chat_tools(shape)
                self._built = (shape, create_agent(self.model, tools=tools, **self.options))
            return self._built[1]

    def _shape(self) -> Shape:
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

    def _chat_tools(self, shape: Shape) -> List[StructuredTool]:
        """The chat as tools: ask_<peer>, run_<command> and, when wanted, ask_user."""
        theirs = {_named(t) for t in self.tools}
        taken  : set = set()
        found  : List[StructuredTool] = []

        def add(name: str, coroutine: Callable[..., Any], description: str) -> None:
            if name in theirs:
                logger.warning("%s: its own tool %r hides the chat's", self.name, name)
                return
            unique, n = name, 2
            while unique in taken:
                unique, n = "%s_%d" % (name[:60], n), n + 1
            taken.add(unique)
            found.append(StructuredTool.from_function(coroutine=coroutine, name=unique,
                                                      description=description))

        peers, commands = shape
        for at, name in peers:
            add(_tool_name("ask_", name), self._asking(at, name),
                "Ask %s, another participant in this chat, and get its answer." % name)
        roster = self.commands()
        for name in commands:
            described = getattr(roster.get(name), "description", "") or "Run the /%s command." % name
            add(_tool_name("run_", name), self._running(name), described)
        if self.ask_user:
            add("ask_user", self._asking(LOCAL, "the user"),
                "Ask the user a question and wait for the answer.")
        return found

    def _asking(self, at: int, name: str) -> Callable[..., Any]:
        async def ask(question: str) -> str:
            try:
                return await self.ask(at, question)
            except Exception as exc:
                return "%s failed: %s" % (name, type(exc).__name__)
        return ask

    def _running(self, name: str) -> Callable[..., Any]:
        async def run(arguments: str = "") -> str:
            try:
                answered = await self.invoke(name, arguments)
            except Exception as exc:
                return "/%s failed: %s" % (name, type(exc).__name__)
            return answered if answered is not None else "(no answer)"
        return run

    # === Memory =====================================================================

    def _history(self, msg: ChatMessage) -> List[BaseMessage]:
        """What ``memory`` selects, without the agent's own tool asks, then the question."""
        history : List[BaseMessage] = []
        if self.memory is not None:
            me     = getattr(self, "peer_id", None)
            roster = self.peers()
            limit  = self.memory.limit
            query  = self.memory if limit is None else self.memory.last(limit + 1)
            earlier = [m for m in self.context(query) if m.id != msg.id]
            if limit is not None:
                earlier = earlier[-limit:] if limit > 0 else []
            # What it asked through its tools, and the answers to that, are not
            # the conversation: they were the work of answering it.
            asked = {m.id for m in earlier if m.frm == me and m.to is not None and m.reply_to is None}
            for m in earlier:
                if m.id in asked or m.reply_to in asked:
                    continue
                history.append(_turn(m, me, roster))
        history.append(HumanMessage(content=msg.text))
        return history


def _turn(m: ChatMessage, me: Optional[int], roster: Dict[int, Any]) -> BaseMessage:
    if m.frm == me:
        return AIMessage(content=m.text)
    if m.frm == LOCAL:
        return HumanMessage(content=m.text)
    who = name_of(roster[m.frm]) if m.frm in roster else str(m.frm)
    return HumanMessage(content="%s: %s" % (who, m.text))


def _result(state: Dict[str, Any]) -> str:
    """The answer in a finished run: the structured response as JSON, else the last message's text."""
    structured = state.get("structured_response")
    if structured is not None:
        dump = getattr(structured, "model_dump_json", None)
        return dump() if callable(dump) else json.dumps(structured, default=str)
    last = next((m for m in reversed(state.get("messages", [])) if isinstance(m, AIMessage)), None)
    if last is None:
        return ""
    if isinstance(last.content, str):
        return last.content
    return "".join(block if isinstance(block, str) else str(block.get("text", ""))
                   for block in last.content
                   if isinstance(block, str) or block.get("type") == "text")
