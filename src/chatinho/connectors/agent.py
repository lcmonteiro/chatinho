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
from typing import Any, Callable, Dict, FrozenSet, Iterable, List, Optional, Sequence, Tuple, TypedDict

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import StructuredTool
from langgraph.graph import END, START, StateGraph

from ..endpoint import Endpoint
from ..hooks import Ask, Commands, Context, Invoke, Peers, Say
from ..hooks import HookAnswer, HookAsk, HookCommands, HookContext, HookInvoke, HookListen, HookPeers, HookSay
from ..hooks import connector, declares, name_of, require
from ..keys import KeyUnavailable, read_async
from ..helpers.memory import MEMORY, earlier, speaker
from ..message import LOCAL, Attachment, ChatMessage, Reply, ReplyStatus
from ..query import Query

logger = logging.getLogger(__name__)

#: What ``create_agent`` takes besides the model and the tools.
OPTIONS : FrozenSet[str] = frozenset(inspect.signature(create_agent).parameters) - {"model", "tools"}

#: What a tool name may hold, for the OpenAI-compatible APIs.
_UNSAFE = re.compile(r"[^A-Za-z0-9_-]")

#: The shape of the chat the agent was built for: its peers (id, name) and commands.
Shape = Tuple[Tuple[Tuple[int, str], ...], Tuple[str, ...]]

#: How a link reminder starts; what follows names the missing links.
REMINDER = "Your answer does not link every file you made."


class AgentInput(TypedDict):
    """What the graph is given: the message to answer or respond to."""

    question : ChatMessage


class AgentOutput(TypedDict):
    """What the graph gives back: the answer and the files the run made."""

    text        : str
    attachments : List[Attachment]


class AgentState(AgentInput, AgentOutput, total=False):
    """The whole state; everything but the output stays in the graph.

    Attributes:
        messages: The run's working messages: memory, the question, then the
            model's calls, tool results and any reminder.
        start: How many of ``messages`` came from memory.
        structured: The agent's structured response, when it has one.
        reminders: How many link reminders this run sent.
        retry: Set by ``verify`` when the model must answer again.
    """

    messages   : List[BaseMessage]
    start      : int
    structured : Any
    reminders  : int
    retry      : bool


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
@require(HookListen)
@require(HookSay)
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
        link_retries: How many times one run sends the model back for a file
            its answer does not link; 0 never does.
        **agent_options: Anything else ``create_agent`` takes
            (``system_prompt``, ``middleware``, ``response_format``,
            ``checkpointer``, ...), passed through unchanged.

    Raises:
        TypeError: An option ``create_agent`` does not take.
    """

    ask      : Ask
    say      : Say
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
        link_retries : int = 1,
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
        self.link_retries = link_retries
        #: The peers and commands that may become tools; None for all.
        self.allowed_peers    : Optional[FrozenSet[str]] = None if peers is None else frozenset(peers)
        self.allowed_commands : Optional[FrozenSet[str]] = None if commands is None else frozenset(commands)
        #: What is passed to create_agent besides the model and the tools.
        self.options : Dict[str, Any] = {"name": name, **agent_options}
        #: The compiled graph, and the shape of the chat it was built for.
        self._built  : Optional[Tuple[Shape, Any]] = None
        #: So two first questions at once build it once.
        self._building = asyncio.Lock()

    def __repr__(self) -> str:
        return "AgentConnector(name=%r)" % self.name

    # === Being asked, being told =====================================================

    async def answer(self, msg: ChatMessage) -> Reply:
        """Runs the graph on the conversation and the question, and answers with its result."""
        try:
            text, files = await self._run(msg)
        except Exception as exc:
            return Reply(self._failed(exc), status=ReplyStatus.ERROR)
        return Reply(text, tuple(files))

    async def listen(self, msg: ChatMessage) -> None:
        """Responds to what the user says to everyone with a say; ignores everyone else.

        A say the session asked of this agent is answered through ``answer``, so
        it is not also responded to here — or the agent would answer it twice.
        """
        asked_me = msg.asked_of is not None and msg.asked_of == getattr(self, "peer_id", None)
        if not (msg.is_broadcast and msg.is_local) or asked_me:
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
        return output["text"], list(output["attachments"])

    def _failed(self, exc: Exception) -> str:
        if isinstance(exc, KeyUnavailable):
            logger.warning("%s: no key (%s)", self.name, exc)
            return "%s: %s" % (self.name, exc)
        # Not its message: a model's error may echo the prompt.
        logger.warning("%s: the agent failed (%s)", self.name, type(exc).__name__)
        return "%s: could not answer (%s)" % (self.name, type(exc).__name__)

    # === The graph ==================================================================

    async def graph(self) -> Any:
        """The compiled graph for the chat as it is now, built or rebuilt as needed."""
        shape = self._shape()
        async with self._building:
            if self._built is None or self._built[0] != shape:
                tools   = self.tools + self._chat_tools(shape)
                # The graph keeps the checkpoints; the agent inside it, run as
                # its subgraph, saves under the same thread.
                options = {k: v for k, v in self.options.items() if k != "checkpointer"}
                inner   = create_agent(self.model, tools=tools, **options)
                self._built = (shape, self._compile(inner))
            return self._built[1]

    def _compile(self, inner: Any) -> Any:
        """``extract -> agent -> verify -(retry)-> agent | -(done)-> load`` around *inner*."""
        retries = self.link_retries

        def extract(state: AgentState) -> Dict[str, Any]:
            messages = self._history(state["question"])
            return {"messages": messages, "start": len(messages) - 1, "reminders": 0, "retry": False}

        async def agent(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
            result = await inner.ainvoke({"messages": state["messages"]}, config=config)
            return {"messages": result["messages"], "structured": result.get("structured_response")}

        def verify(state: AgentState) -> Dict[str, Any]:
            missing = [f.name for f in _files(state) if "](%s)" % f.name not in _text(state)]
            sent    = state.get("reminders", 0)
            if not missing or sent >= retries:
                return {"retry": False}
            links    = ", ".join("[<title>](%s)" % name for name in missing)
            reminder = HumanMessage(content="%s Answer again and include %s." % (REMINDER, links))
            return {"messages": [*state["messages"], reminder], "reminders": sent + 1, "retry": True}

        def load(state: AgentState) -> Dict[str, Any]:
            return {"text": _text(state), "attachments": _files(state)}

        graph = StateGraph(AgentState, input_schema=AgentInput, output_schema=AgentOutput)
        graph.add_node("extract", extract)
        graph.add_node("agent", agent)
        graph.add_node("verify", verify)
        graph.add_node("load", load)
        graph.add_edge(START, "extract")
        graph.add_edge("extract", "agent")
        graph.add_edge("agent", "verify")
        graph.add_conditional_edges("verify", lambda state: "agent" if state.get("retry") else "load",
                                    ["agent", "load"])
        graph.add_edge("load", END)
        return graph.compile(checkpointer=self.options.get("checkpointer"), name=self.options.get("name"))

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
        async def ask(question: str) -> Reply:
            try:
                return await self.ask(at, question)
            except Exception as exc:
                # Only the type: an exception may echo a prompt.
                return Reply("%s failed: %s" % (name, type(exc).__name__), status=ReplyStatus.ERROR)
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
        """For each of its own messages whose parent ``memory`` left out, that parent.

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


def _text(state: AgentState) -> str:
    """The run's answer: the structured response as JSON, else the last message's text."""
    structured = state.get("structured")
    if structured is not None:
        dump = getattr(structured, "model_dump_json", None)
        return dump() if callable(dump) else json.dumps(structured, default=str)
    run  = state["messages"][state["start"]:]
    last = next((m for m in reversed(run) if isinstance(m, AIMessage)), None)
    if last is None:
        return ""
    if isinstance(last.content, str):
        return last.content
    return "".join(block if isinstance(block, str) else str(block.get("text", ""))
                   for block in last.content
                   if isinstance(block, str) or block.get("type") == "text")


def _files(state: AgentState) -> List[Attachment]:
    """The files this run's tools made, the last of each name, in the order first made."""
    found : Dict[str, Attachment] = {}
    for m in state["messages"][state["start"]:]:
        made = _attachment(m.artifact) if isinstance(m, ToolMessage) else None
        if made is not None:
            found[made.name] = made
    return list(found.values())


def _attachment(artifact: Any) -> Optional[Attachment]:
    """*artifact* as an Attachment, when it is one or looks like one."""
    if isinstance(artifact, Attachment):
        return artifact
    name, media_type = getattr(artifact, "name", None), getattr(artifact, "media_type", None)
    data = getattr(artifact, "data", None)
    if not (isinstance(name, str) and isinstance(media_type, str) and isinstance(data, (str, bytes))):
        return None
    return Attachment(name=name, media_type=media_type,
                      data=data.encode("utf-8") if isinstance(data, str) else data)
