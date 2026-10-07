"""A chatinho session served over MCP, in place of a terminal.

:class:`McpFrontend` is the session's peer zero, as a terminal would be, but
nobody types into it: MCP clients put questions to the session through it. It
speaks the modern MCP protocol (2026-07-28) over Streamable HTTP, with a bearer
token on every request. The protocol is stateless: every request
names its client, and may carry credentials the client lends for that question.

The frontend speaks for every client itself. It receives a question, forwards
it into the session as its own message — an ask to the only peer that can
answer, or a say to the room when several can — and sends the reply to that
message back to the client that asked. No peer is added per client: questions
are told apart by their message ids.
"""

import asyncio
import hmac
import logging
import secrets
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import mcp_types as types
from mcp.server.lowlevel.server import Server

from chatinho.chat_hooks import (
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
    Invoke,
    Locate,
    Peers,
    Say,
    declares,
    frontend,
    require,
)
from chatinho.chat_message import LOCAL, Answer, Attachment, ChatMessage, MessageID, Reply, Secret
from chatinho import mcp_wire as wire

logger = logging.getLogger(__name__)

#: What a peer is told when it asks the person this frontend stands in for.
_NOBODY_HERE = "Nobody is at this session's terminal: it is served over MCP"


@dataclass(eq=False)
class _Question:
    """One question in flight, from its ``ask`` call to its one result."""

    token       : str
    client      : str
    asker       : Tuple[str, str]
    deadline    : float
    credentials : Dict[str, Secret]
    answer      : "asyncio.Future[Tuple[str, str, Optional[MessageID]]]"
    seconds     : float = 0.0
    msg_id      : Optional[MessageID] = None
    task        : Optional["asyncio.Task[Any]"] = None
    closed      : bool = False


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
                "asker"       : {"type": "string", "description": "Who asks, to keep follow-ups together."},
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
@require(HookAsk)
@require(HookSay)
@require(HookListen)
@require(HookInvoke)
@require(HookPeers)
@require(HookCommands)
@require(HookContext)
@require(HookLocate)
@require(HookAnswer)
@require(HookServeCredential)
class McpFrontend:
    """Serves a session over MCP, in place of a terminal.

    Args:
        name: Its name in the session, and the server's name; ``master`` by default.
        token: The bearer token every request must carry; required.
        host: Where the server listens.
        port: The server's port.
        deadline: How long a question may take when its client does not say,
            in seconds.
        credentials: The credentials the session's peers may use, by name, each
            with a short description; announced at discovery. Others are dropped.

    Raises:
        ValueError: No token, or a non-positive deadline.
    """

    ask      : Ask
    say      : Say
    invoke   : Invoke
    peers    : Peers
    commands : Commands
    context  : Context
    locate   : Locate

    def __init__(
        self,
        name        : str = "master",
        *,
        token       : str,
        host        : str = "127.0.0.1",
        port        : int = 8000,
        deadline    : float = wire.DEFAULT_DEADLINE,
        credentials : Optional[Dict[str, str]] = None,
    ) -> None:
        if not token:
            raise ValueError("McpFrontend needs a bearer token")
        if deadline <= 0:
            raise ValueError("deadline must be positive")
        self.name        = name
        self.host        = host
        self.port        = port
        self.deadline    = float(deadline)
        self.credentials : Dict[str, str] = dict(credentials or {})
        self._token      = token
        #: The MCP server itself; an in-process client can connect to it directly.
        self.server : Server[Any] = Server(name, on_list_tools=self._list_tools, on_call_tool=self._call_tool)
        if self.credentials:
            self.server.extensions[wire.CREDENTIALS_KEY] = dict(self.credentials)
        #: Open questions, so shutting down can close them.
        self._open    : Dict[str, _Question] = {}
        #: Open questions, by the id of the message the frontend forwarded them as.
        self._by_msg  : Dict[MessageID, _Question] = {}
        #: Questions said to the room, by id, waiting for their first reply.
        self._waiting : Dict[MessageID, "asyncio.Future[ChatMessage]"] = {}
        #: Each asker's last answer in the room, so its next question replies to it.
        self._last_heard : Dict[Tuple[str, str], MessageID] = {}
        #: One question opens at a time, so each finds its own message.
        self._opening = asyncio.Lock()
        self._http    : Any = None

    # === Being peer zero ============================================================

    async def answer(self, msg: ChatMessage) -> Optional[Reply]:
        """A peer asked the person, and there is none; an answer that came late is only heard."""
        if msg.reply_to is not None:
            return None
        return Reply(_NOBODY_HERE, status="error")

    async def listen(self, msg: ChatMessage) -> None:
        """Hands the first reply to a question said to the room back to the client waiting on it."""
        if msg.reply_to is None:
            return
        waiting = self._waiting.pop(msg.reply_to, None)
        if waiting is not None and not waiting.done():
            waiting.set_result(msg)

    async def serve(self) -> None:
        """Serves MCP over HTTP until the server stops, which ends the chat."""
        import uvicorn
        app    = _BearerOnly(self.server.streamable_http_app(host=self.host), self._token)
        config = uvicorn.Config(app, host=self.host, port=self.port, log_level="warning")
        self._http = uvicorn.Server(config)
        await self._http.serve()

    def shutdown(self) -> None:
        """Stops the HTTP server and closes every open question."""
        if self._http is not None:
            self._http.should_exit = True
        for question in list(self._open.values()):
            self._close(question)

    # === Lending to whoever answers =================================================

    async def serve_credential(self, msg_id: MessageID, name: str) -> str:
        """The credential *name* lent with the question *msg_id*, while it is open."""
        question = self._question_of(msg_id)
        if question is None or question.closed or name not in question.credentials:
            raise CredentialUnavailable("No credential %r was lent for %s" % (name, msg_id))
        return question.credentials[name].reveal()

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
        text = args.get("text")
        if not isinstance(text, str) or not text.strip():
            return wire.result("error", "ask needs a text")
        deadline = args.get("deadline_ms")
        seconds  = deadline / 1000.0 if isinstance(deadline, int) and deadline > 0 else self.deadline
        opened   = await self._open_question(client, args.get("asker"), text, seconds, meta)
        if isinstance(opened, types.CallToolResult):
            return opened
        try:
            return await self._wait(opened)
        finally:
            self._close(opened)               # however the call ended, even cancelled

    async def _tool_invoke(self, client: str, args: Dict[str, Any]) -> types.CallToolResult:
        name = args.get("name")
        if not isinstance(name, str) or not name:
            return wire.result("error", "invoke needs a command name")
        said = await self.invoke(name, str(args.get("args") or ""))
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
        """Forwards *text* into the session as the frontend's own message; an error result if it cannot."""
        answering = self._answering()
        if not answering:
            return wire.result("error", "No peer in this session can answer")
        if len(answering) > 1 and not any(declares(who, HookListen) for _, who in answering):
            return wire.result(
                "error", "Several peers could answer and none listens to the room; a peer router is needed")

        loop     = asyncio.get_running_loop()
        question = _Question(
            token       = secrets.token_urlsafe(18),
            client      = client,
            asker       = (client, wire.safe_name(asker, "")),
            deadline    = loop.time() + seconds,
            credentials = self._lent(meta),
            answer      = loop.create_future(),
            seconds     = seconds,
        )
        self._open[question.token] = question

        async with self._opening:
            if len(answering) == 1:
                at   = answering[0][0]
                task = asyncio.create_task(self.ask(at, text, detail=True))
                await asyncio.sleep(0)                 # lets the ask post its question
                question.task   = task
                question.msg_id = self._posted(at, text)
                task.add_done_callback(lambda done: _settle_direct(question, done))
            else:
                msg_id  = await self.say(text, reply_to=self._last_heard.get(question.asker))
                waiting : "asyncio.Future[ChatMessage]" = loop.create_future()
                self._waiting[msg_id] = waiting
                question.msg_id = msg_id
                waiting.add_done_callback(lambda done: _settle_broadcast(question, done))
            if question.msg_id is not None:
                self._by_msg[question.msg_id] = question
        return question

    async def _wait(self, question: _Question) -> types.CallToolResult:
        """Waits for the answer or the deadline, whichever is first."""
        remaining = question.deadline - asyncio.get_running_loop().time()
        if remaining > 0:
            await asyncio.wait({question.answer}, timeout=remaining)
        return await self._finish(question, timed_out=not question.answer.done())

    async def _finish(self, question: _Question, timed_out: bool = False) -> types.CallToolResult:
        """Ends the question and builds its one result."""
        self._close(question)
        if timed_out and not question.answer.done():
            return wire.result("timeout", "No answer within %g seconds" % question.seconds)
        status, text, msg_id = question.answer.result()
        if question.task is None:
            # In the room every reply reads as answered, so a question back
            # cannot be told apart: the next question replies to the last answer.
            if msg_id is not None:
                self._last_heard[question.asker] = msg_id
        attachments = await self._attachments_of(msg_id, text) if msg_id is not None else []
        return wire.result(status, text, attachments, str(msg_id) if msg_id is not None else None)

    def _close(self, question: _Question) -> None:
        """Lets go of everything a question held: its wait and its credentials."""
        if question.closed:
            return
        question.closed = True
        self._open.pop(question.token, None)
        if question.msg_id is not None:
            self._by_msg.pop(question.msg_id, None)
            self._waiting.pop(question.msg_id, None)
        if question.task is not None and not question.task.done():
            question.task.cancel()
        question.credentials.clear()

    # === Helpers ====================================================================

    def _answering(self) -> List[Tuple[int, Any]]:
        """The peers that can answer: everyone but the frontend that declares HookAnswer."""
        return [(at, who) for at, who in sorted(self.peers().items())
                if at != LOCAL and declares(who, HookAnswer)]

    def _answering_names(self) -> List[Tuple[int, str]]:
        return [(at, str(getattr(who, "name", type(who).__name__))) for at, who in self._answering()]

    def _posted(self, at: int, text: str) -> Optional[MessageID]:
        """The question the frontend just put to *at*: its newest one not already open."""
        for msg in reversed(self.context()):
            if msg.frm == LOCAL and msg.to == at and msg.text == text and msg.id not in self._by_msg:
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
    if exc is not None:
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
