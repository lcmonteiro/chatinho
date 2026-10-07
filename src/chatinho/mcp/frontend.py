"""A chatinho session served over MCP, in place of a terminal.

:class:`McpFrontend` is the session's peer zero, as a terminal would be, but
nobody types into it: MCP clients put questions to the session through it. It
speaks the modern MCP protocol (2026-07-28), which is stateless — every request
names its client — and asks for input mid-call by returning an
``InputRequiredResult`` that the client fulfils and retries.

Each asker becomes a proxy peer named ``<client>/<asker>``, so the session's
peers see who is asking. The session, not the client, decides who answers: its
only answering peer is asked directly; with several, the question is said to
the room and the first reply to it is the answer.
"""

import asyncio
import hmac
import logging
import secrets
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import mcp_types as types
from mcp.server.lowlevel.server import Server

from ..chat_hooks import (
    Ask,
    Commands,
    Context,
    CredentialUnavailable,
    HookAnswer,
    HookAsk,
    HookCommands,
    HookContext,
    HookInvoke,
    HookListen,
    HookLocate,
    HookPeers,
    HookSay,
    HookServeCredential,
    HookServeSample,
    Invoke,
    Locate,
    PeerRemoved,
    Peers,
    SamplingUnavailable,
    Say,
    connector,
    declares,
    frontend,
    require,
)
from ..chat_message import LOCAL, Answer, Attachment, ChatMessage, MessageID, Reply, Secret
from . import wire

logger = logging.getLogger(__name__)

#: What a peer is told when it asks the person this frontend stands in for.
_NOBODY_HERE = "Nobody is at this session's terminal: it is served over MCP"


@connector("asker")
@require(HookAsk)
@require(HookSay)
@require(HookListen)
@require(HookAnswer)
@require(HookInvoke)
class _AskerProxy:
    """One remote asker, as a peer of the session.

    Questions from that asker are asked or said in its name. It catches the
    first reply to each question it said to the room, and it cannot be asked:
    there is nobody behind it to answer.
    """

    ask    : Ask
    say    : Say
    invoke : Invoke

    def __init__(self, name: str) -> None:
        self.name = name
        #: Questions said to the room, by id, and who is waiting on each.
        self.waiting : Dict[MessageID, "asyncio.Future[ChatMessage]"] = {}
        #: How many of its questions are open now.
        self.open : int = 0
        #: When it last asked or got an answer, for the idle sweep.
        self.last_active : float = time.monotonic()
        #: The last answer it got in the room, so its next question there replies to it.
        self.last_heard : Optional[MessageID] = None
        #: One question opens at a time, so each finds its own message.
        self.opening = asyncio.Lock()

    async def listen(self, msg: ChatMessage) -> None:
        """Hands the first reply to a question it said to whoever waits on it."""
        if msg.reply_to is None:
            return
        waiting = self.waiting.pop(msg.reply_to, None)
        if waiting is not None and not waiting.done():
            waiting.set_result(msg)

    async def answer(self, msg: ChatMessage) -> Optional[Reply]:
        """Refuses questions; an answer arriving after its question ended is only heard."""
        if msg.reply_to is not None:
            return None
        return Reply("%s stands for a remote asker and cannot be asked" % self.name, status="error")


@dataclass(eq=False)
class _Question:
    """One question in flight, across however many rounds its ``ask`` takes."""

    token       : str
    client      : str
    proxy       : _AskerProxy
    deadline    : float
    can_sample  : bool
    credentials : Dict[str, Secret]
    answer      : "asyncio.Future[Tuple[str, str, Optional[MessageID]]]"
    seconds     : float = 0.0
    msg_id      : Optional[MessageID] = None
    task        : Optional["asyncio.Task[Any]"] = None
    #: Samples peers asked for that the client has not been sent yet.
    queued      : Dict[str, Tuple[types.CreateMessageRequest, "asyncio.Future[str]"]] = field(
        default_factory=dict)
    #: Samples sent to the client, waiting for its retry.
    sent        : Dict[str, "asyncio.Future[str]"] = field(default_factory=dict)
    wake        : asyncio.Event = field(default_factory=asyncio.Event)
    closed      : bool = False
    timer       : Optional[asyncio.TimerHandle] = None
    count       : int = 0


_TOOLS = [
    types.Tool(
        name="ask",
        description=(
            "Put a question to this chatinho session. The session decides which of its peers answers. "
            "The result is exactly one of: answered, asked (a question back to you), error or timeout."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "text"        : {"type": "string", "description": "The question."},
                "asker"       : {"type": "string", "description": "Who asks; shown as <client>/<asker>."},
                "deadline_ms" : {"type": "integer", "minimum": 1, "description": "How long to wait, in ms."},
            },
            "required": ["text"],
        },
    ),
    types.Tool(
        name="list_peers",
        description="The names of the peers that can answer in this session.",
        input_schema={"type": "object", "properties": {}},
    ),
    types.Tool(
        name="list_commands",
        description="The commands this session can run, with what each does.",
        input_schema={"type": "object", "properties": {}},
    ),
    types.Tool(
        name="invoke",
        description="Run one of this session's commands by name, and get what it answered.",
        input_schema={
            "type": "object",
            "properties": {
                "name"  : {"type": "string"},
                "args"  : {"type": "string"},
                "asker" : {"type": "string"},
            },
            "required": ["name"],
        },
    ),
    types.Tool(
        name="read_attachment",
        description="Read an attachment of an earlier answer, by the answer's msg_id and its name.",
        input_schema={
            "type": "object",
            "properties": {"msg_id": {"type": "string"}, "name": {"type": "string"}},
            "required": ["msg_id", "name"],
        },
    ),
]


@frontend("master")
@require(HookPeers)
@require(HookCommands)
@require(HookContext)
@require(HookLocate)
@require(HookAnswer)
@require(HookServeSample)
@require(HookServeCredential)
class McpFrontend:
    """Serves a session over MCP, in place of a terminal.

    Args:
        name: Its name in the session, and the server's name; ``master`` by default.
        transport: ``"stdio"`` or ``"http"`` (Streamable HTTP).
        host: Where the HTTP transport listens.
        port: The HTTP transport's port.
        token: The bearer token every HTTP request must carry; required for HTTP.
        deadline: How long a question may take when its client does not say,
            in seconds.
        idle: How long an asker's proxy stays with no question open, in seconds.
        credentials: The credentials the session's peers may use, by name, each
            with a short description; announced at discovery. Others are dropped.

    Raises:
        ValueError: An unknown transport, HTTP without a token, or a
            non-positive deadline or idle time.
    """

    peers    : Peers
    commands : Commands
    context  : Context
    locate   : Locate

    def __init__(
        self,
        name        : str = "master",
        *,
        transport   : str = "stdio",
        host        : str = "127.0.0.1",
        port        : int = 8000,
        token       : Optional[str] = None,
        deadline    : float = wire.DEFAULT_DEADLINE,
        idle        : float = 600.0,
        credentials : Optional[Dict[str, str]] = None,
    ) -> None:
        if transport not in ("stdio", "http"):
            raise ValueError("transport is 'stdio' or 'http', got %r" % (transport,))
        if transport == "http" and not token:
            raise ValueError("The HTTP transport needs a bearer token")
        if deadline <= 0 or idle <= 0:
            raise ValueError("deadline and idle must be positive")
        self.name        = name
        self.transport   = transport
        self.host        = host
        self.port        = port
        self.deadline    = float(deadline)
        self.idle        = float(idle)
        self.credentials : Dict[str, str] = dict(credentials or {})
        self._token      = token
        #: The MCP server itself; an in-process client can connect to it directly.
        self.server : Server[Any] = Server(name, on_list_tools=self._list_tools, on_call_tool=self._call_tool)
        if self.credentials:
            self.server.extensions[wire.CREDENTIALS_KEY] = dict(self.credentials)
        self._proxies : Dict[Tuple[str, str], _AskerProxy] = {}
        self._open    : Dict[str, _Question] = {}
        self._by_msg  : Dict[MessageID, _Question] = {}
        self._sweeper : Optional["asyncio.Task[None]"] = None
        self._http    : Any = None

    # === Being peer zero ============================================================

    async def answer(self, msg: ChatMessage) -> Reply:
        """A peer asked the person; there is none here to answer."""
        return Reply(_NOBODY_HERE, status="error")

    async def serve(self) -> None:
        """Serves MCP until the transport closes, which ends the chat."""
        if self.transport == "stdio":
            from mcp.server.stdio import stdio_server
            async with stdio_server() as (read, write):
                await self.server.run(read, write, self.server.create_initialization_options())
            return
        import uvicorn
        app    = _BearerOnly(self.server.streamable_http_app(host=self.host), self._token or "")
        config = uvicorn.Config(app, host=self.host, port=self.port, log_level="warning")
        self._http = uvicorn.Server(config)
        await self._http.serve()

    def shutdown(self) -> None:
        """Stops the sweep and closes every open question."""
        if self._sweeper is not None:
            self._sweeper.cancel()
            self._sweeper = None
        if self._http is not None:
            self._http.should_exit = True
        for question in list(self._open.values()):
            self._close(question)

    # === Lending to whoever answers =================================================

    async def serve_sample(
        self,
        msg_id     : MessageID,
        messages   : Sequence[Dict[str, str]],
        max_tokens : Optional[int],
        system     : Optional[str],
    ) -> str:
        """Asks the client behind *msg_id* for a completion, in the question's next round."""
        question = self._question_of(msg_id)
        if question is None or question.closed:
            raise SamplingUnavailable("No remote asker is waiting on %s" % msg_id)
        if not question.can_sample:
            raise SamplingUnavailable("%s does not run completions" % question.client)
        request = types.CreateMessageRequest(params=types.CreateMessageRequestParams(
            messages=[types.SamplingMessage(role=_role(m), content=types.TextContent(text=str(m["content"])))
                      for m in messages],
            max_tokens=max_tokens or 1024,
            system_prompt=system,
        ))
        question.count += 1
        future : "asyncio.Future[str]" = asyncio.get_running_loop().create_future()
        question.queued["sample-%d" % question.count] = (request, future)
        question.wake.set()
        return await future

    async def serve_credential(self, msg_id: MessageID, name: str) -> str:
        """The credential *name* lent with the question *msg_id*, while it is open."""
        question = self._question_of(msg_id)
        if question is None or question.closed or name not in question.credentials:
            raise CredentialUnavailable("No credential %r was lent for %s" % (name, msg_id))
        return question.credentials[name].reveal()

    # === The idle sweep =============================================================

    def sweep(self, now: Optional[float] = None) -> int:
        """Removes the proxies that have had nothing open for the idle time.

        Args:
            now: The ``time.monotonic()`` to measure against; now when None.

        Returns:
            int: How many proxies left.
        """
        now     = time.monotonic() if now is None else now
        session = self._session()
        gone    = 0
        for key, proxy in list(self._proxies.items()):
            if proxy.open or now - proxy.last_active < self.idle:
                continue
            del self._proxies[key]
            at = getattr(proxy, "peer_id", None)
            if session is not None and at in self.peers():
                session.remove_connector(at)
            gone += 1
        return gone

    async def _sweep_forever(self) -> None:
        while True:
            await asyncio.sleep(min(max(self.idle / 2, 0.01), 30.0))
            self.sweep()

    # === MCP ========================================================================

    async def _list_tools(self, ctx: Any, params: Any) -> types.ListToolsResult:
        return types.ListToolsResult(tools=list(_TOOLS))

    async def _call_tool(self, ctx: Any, params: types.CallToolRequestParams) -> Any:
        meta   = dict(ctx.meta or {})
        info   = meta.get(types.CLIENT_INFO_META_KEY) or {}
        client = wire.safe_name(info.get("name") if isinstance(info, dict) else None, "client")
        args   = params.arguments or {}
        try:
            if params.name == "ask":
                return await self._tool_ask(client, args, params, meta)
            if params.name == "list_peers":
                return _listing("peers", [name for _, name in self._answering_names()])
            if params.name == "list_commands":
                return _listing("commands", [
                    {"name": name, "description": str(getattr(cmd, "description", ""))}
                    for name, cmd in sorted(self.commands().items())
                ])
            if params.name == "invoke":
                return await self._tool_invoke(client, args)
            if params.name == "read_attachment":
                return await self._tool_read_attachment(args)
        except Exception as exc:
            logger.error("%s failed for %s", params.name, client, exc_info=True)
            return wire.result("error", "%s failed: %s" % (params.name, type(exc).__name__))
        return wire.result("error", "No tool named %r" % params.name)

    async def _tool_ask(
        self, client: str, args: Dict[str, Any], params: types.CallToolRequestParams, meta: Dict[str, Any],
    ) -> Any:
        if params.request_state is not None:
            question = self._open.get(params.request_state)
            if question is None or question.closed or question.client != client:
                return wire.result("error", "That question is no longer open")
            self._take(question, params.input_responses or {})
            return await self._wait(question)

        text = args.get("text")
        if not isinstance(text, str) or not text.strip():
            return wire.result("error", "ask needs a text")
        deadline = args.get("deadline_ms")
        seconds  = deadline / 1000.0 if isinstance(deadline, int) and deadline > 0 else self.deadline
        opened   = await self._open_question(client, args.get("asker"), text, seconds, meta)
        if isinstance(opened, types.CallToolResult):
            return opened
        return await self._wait(opened)

    async def _tool_invoke(self, client: str, args: Dict[str, Any]) -> types.CallToolResult:
        name = args.get("name")
        if not isinstance(name, str) or not name:
            return wire.result("error", "invoke needs a command name")
        proxy = await self._proxy_for(client, args.get("asker"))
        proxy.last_active = time.monotonic()
        said  = await proxy.invoke(name, str(args.get("args") or ""))
        if said is None:
            return wire.result("error", "No command /%s, or it wrote its output rather than answering" % name)
        return wire.result("answered", said)

    async def _tool_read_attachment(self, args: Dict[str, Any]) -> types.CallToolResult:
        try:
            msg_id = MessageID.parse(str(args.get("msg_id")))
        except ValueError:
            return wire.result("error", "msg_id is not a message id")
        name = str(args.get("name") or "")
        data = wire.read_link(await self.locate(msg_id, name))
        if data is None:
            return wire.result("error", "No attachment %r on %s" % (name, msg_id))
        return wire.result("answered", name, [Attachment(name, wire.media_type_of(name), data)], str(msg_id))

    # === One question ===============================================================

    async def _open_question(
        self, client: str, asker: Any, text: str, seconds: float, meta: Dict[str, Any],
    ) -> Any:
        """Puts *text* to the session from the asker's proxy; an error result if it cannot."""
        if self._session() is None:
            return wire.result("error", "This frontend is not attached to a session")
        answering = self._answering()
        if not answering:
            return wire.result("error", "No peer in this session can answer")
        if len(answering) > 1 and not any(declares(who, HookListen) for _, who in answering):
            return wire.result(
                "error", "Several peers could answer and none listens to the room; a peer router is needed")

        proxy    = await self._proxy_for(client, asker)
        loop     = asyncio.get_running_loop()
        caps     = meta.get(types.CLIENT_CAPABILITIES_META_KEY) or {}
        question = _Question(
            token       = secrets.token_urlsafe(18),
            client      = client,
            proxy       = proxy,
            deadline    = loop.time() + seconds,
            can_sample  = isinstance(caps, dict) and caps.get("sampling") is not None,
            credentials = self._lent(meta),
            answer      = loop.create_future(),
            seconds     = seconds,
        )
        proxy.open       += 1
        proxy.last_active = time.monotonic()
        self._open[question.token] = question
        # A client that never comes back for its answer must not hold it forever.
        question.timer = loop.call_at(question.deadline + 1.0, self._close, question)

        async with proxy.opening:
            if len(answering) == 1:
                at   = answering[0][0]
                task = asyncio.create_task(proxy.ask(at, text, detail=True))
                await asyncio.sleep(0)                 # lets the ask post its question
                question.task   = task
                question.msg_id = self._posted_by(proxy, at, text)
                task.add_done_callback(lambda done: _settle_direct(question, done))
            else:
                msg_id  = await proxy.say(text, reply_to=proxy.last_heard)
                waiting : "asyncio.Future[ChatMessage]" = loop.create_future()
                proxy.waiting[msg_id] = waiting
                question.msg_id = msg_id
                waiting.add_done_callback(lambda done: _settle_broadcast(question, done))
        if question.msg_id is not None:
            self._by_msg[question.msg_id] = question
        return question

    async def _wait(self, question: _Question) -> Any:
        """Waits for the answer, a sample to send, or the deadline — whichever is first."""
        loop = asyncio.get_running_loop()
        while True:
            if question.answer.done():
                return await self._finish(question)
            if question.queued:
                return self._input_required(question)
            remaining = question.deadline - loop.time()
            if remaining <= 0:
                return await self._finish(question, timed_out=True)
            question.wake.clear()
            woken : "asyncio.Future[Any]" = asyncio.ensure_future(question.wake.wait())
            pending : set = {question.answer, woken}
            try:
                await asyncio.wait(pending, timeout=remaining, return_when=asyncio.FIRST_COMPLETED)
            finally:
                woken.cancel()

    def _input_required(self, question: _Question) -> types.InputRequiredResult:
        """Sends every queued sample to the client in one round."""
        requests: Dict[str, Any] = {}
        for key, (request, future) in question.queued.items():
            requests[key] = request
            question.sent[key] = future
        question.queued.clear()
        return types.InputRequiredResult(input_requests=requests, request_state=question.token)

    def _take(self, question: _Question, responses: Dict[str, Any]) -> None:
        """Resolves the samples the client answered; the rest it did not send are refused."""
        for key, future in list(question.sent.items()):
            del question.sent[key]
            if future.done():
                continue
            text = _completion(responses.get(key))
            if text is None:
                future.set_exception(SamplingUnavailable("%s sent no completion" % question.client))
            else:
                future.set_result(text)

    async def _finish(self, question: _Question, timed_out: bool = False) -> types.CallToolResult:
        """Ends the question and builds its one result."""
        self._close(question)
        if timed_out and not question.answer.done():
            return wire.result("timeout", "No answer within %g seconds" % question.seconds)
        status, text, msg_id = question.answer.result()
        if question.task is None:
            # In the room every reply reads as answered, so a question back
            # cannot be told apart: the next question replies to the last answer.
            question.proxy.last_heard = msg_id
        attachments = await self._attachments_of(msg_id, text) if msg_id is not None else []
        return wire.result(status, text, attachments, str(msg_id) if msg_id is not None else None)

    def _close(self, question: _Question) -> None:
        """Lets go of everything a question held: its wait, its samples, its credentials."""
        if question.closed:
            return
        question.closed = True
        self._open.pop(question.token, None)
        if question.msg_id is not None:
            self._by_msg.pop(question.msg_id, None)
            question.proxy.waiting.pop(question.msg_id, None)
        if question.timer is not None:
            question.timer.cancel()
        if question.task is not None and not question.task.done():
            question.task.cancel()
        for _, future in list(question.queued.values()):
            _refuse(future)
        for future in list(question.sent.values()):
            _refuse(future)
        question.queued.clear()
        question.sent.clear()
        question.credentials.clear()
        question.proxy.open = max(0, question.proxy.open - 1)
        question.proxy.last_active = time.monotonic()

    # === Helpers ====================================================================

    def _session(self) -> Any:
        """The session this frontend serves.

        A grant is the session's own bound method, so it reaches back to the
        session — the cost docs/SPEC.md §7 names. Proxies come and go with the
        askers, and adding or removing a peer is the session's to do.
        """
        return getattr(self.peers, "__self__", None)

    def _answering(self) -> List[Tuple[int, Any]]:
        """The peers that can answer: not the frontend, not an asker's proxy."""
        return [(at, who) for at, who in sorted(self.peers().items())
                if at != LOCAL and not isinstance(who, _AskerProxy) and declares(who, HookAnswer)]

    def _answering_names(self) -> List[Tuple[int, str]]:
        return [(at, str(getattr(who, "name", type(who).__name__))) for at, who in self._answering()]

    async def _proxy_for(self, client: str, asker: Any) -> _AskerProxy:
        """The asker's proxy, added to the session the first time it asks."""
        own   = wire.safe_name(asker, "")
        key   = (client, own)
        proxy = self._proxies.get(key)
        if proxy is not None and getattr(proxy, "peer_id", None) in self.peers():
            return proxy
        proxy   = _AskerProxy("%s/%s" % (client, own) if own else client)
        session = self._session()
        session.add_connector(proxy)
        await session.start()
        self._proxies[key] = proxy
        if self._sweeper is None or self._sweeper.done():
            self._sweeper = asyncio.create_task(self._sweep_forever())
        return proxy

    def _posted_by(self, proxy: _AskerProxy, at: int, text: str) -> Optional[MessageID]:
        """The question the proxy just put to *at*: its newest one not already open."""
        for msg in reversed(self.context()):
            if msg.frm == getattr(proxy, "peer_id", None) and msg.to == at and msg.text == text \
                    and msg.id not in self._by_msg:
                return msg.id
        return None

    def _question_of(self, msg_id: MessageID) -> Optional[_Question]:
        return self._by_msg.get(msg_id)

    def _lent(self, meta: Dict[str, Any]) -> Dict[str, Secret]:
        """The declared credentials lent with a question, wrapped so they never show."""
        lent = meta.get(wire.CREDENTIALS_KEY)
        if not isinstance(lent, dict):
            return {}
        return {name: Secret(value) for name, value in lent.items()
                if name in self.credentials and isinstance(value, str)}

    async def _attachments_of(self, msg_id: MessageID, text: str) -> List[Attachment]:
        """What an answer attached: each name it links to that the backend can read back."""
        found: List[Attachment] = []
        for name in wire.linked_names(text):
            data = wire.read_link(await self.locate(msg_id, name))
            if data is not None:
                found.append(Attachment(name, wire.media_type_of(name), data))
        return found


def _settle_direct(question: _Question, task: "asyncio.Task[Any]") -> None:
    """Turns how the direct ask ended into the question's outcome."""
    if question.answer.done():
        return
    if task.cancelled():
        question.answer.set_result(("error", "The question was withdrawn", None))
        return
    exc = task.exception()
    if isinstance(exc, PeerRemoved):
        question.answer.set_result(("error", "The peer left before answering", None))
    elif exc is not None:
        question.answer.set_result(("error", "The peer failed: %s" % type(exc).__name__, None))
    else:
        got = task.result()
        if isinstance(got, Answer):
            question.answer.set_result((got.status, got.text, got.msg_id))
        else:
            question.answer.set_result(("answered", str(got), None))


def _settle_broadcast(question: _Question, waiting: "asyncio.Future[ChatMessage]") -> None:
    """The first reply to a question said to the room is its answer."""
    if question.answer.done() or waiting.cancelled():
        return
    reply = waiting.result()
    question.answer.set_result(("answered", reply.text, reply.id))


def _refuse(future: "asyncio.Future[str]") -> None:
    if not future.done():
        future.set_exception(SamplingUnavailable("The question ended before the client answered"))


def _role(message: Dict[str, str]) -> Any:
    role = message.get("role")
    if role not in ("user", "assistant"):
        raise ValueError("A sampling message's role is 'user' or 'assistant', got %r" % (role,))
    return role


def _completion(response: Any) -> Optional[str]:
    """The text of a client's completion, or None when it sent none."""
    content = getattr(response, "content", None)
    if isinstance(content, types.TextContent):
        return content.text
    if isinstance(content, list):
        texts = [block.text for block in content if isinstance(block, types.TextContent)]
        return "".join(texts) if texts else None
    return None


def _listing(key: str, items: List[Any]) -> types.CallToolResult:
    """A plain listing, as text and as structured content."""
    lines = [item if isinstance(item, str) else "%s — %s" % (item["name"], item["description"])
             for item in items]
    return types.CallToolResult(
        content=[types.TextContent(text="\n".join(lines) or "(none)")],
        structured_content={key: items},
    )


class _BearerOnly:
    """An ASGI wrapper that refuses every HTTP request without the bearer token."""

    def __init__(self, app: Any, token: str) -> None:
        self.app   = app
        self.token = token.encode()

    async def __call__(self, scope: Dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") == "http":
            sent = dict(scope.get("headers") or []).get(b"authorization", b"")
            if not (sent.startswith(b"Bearer ") and hmac.compare_digest(sent[7:], self.token)):
                await send({"type": "http.response.start", "status": 401,
                            "headers": [(b"content-type", b"text/plain"), (b"www-authenticate", b"Bearer")]})
                await send({"type": "http.response.body", "body": b"Unauthorized"})
                return
        await self.app(scope, receive, send)
