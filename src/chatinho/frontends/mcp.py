"""A chatinho session served over MCP, in place of a terminal.

:class:`McpFrontend` is the session's peer zero, as a terminal would be, but
nobody types into it. Its tools are what a person at the terminal can do:

- ``say``: say something in the session and get the first reply to it. When
  one peer answers there, the session asks it of that peer; when several do,
  it is said to the room.
- ``ask``: ask one peer, by name, and get its answer.
- ``peers``: who is in the session, and which of them answer.
- ``tools``: the session's tools (its slash commands).
- ``run``: run one of them, and get what it answered.

It speaks the modern MCP protocol (2026-07-28) over Streamable HTTP, with a
bearer token on every request. The protocol is stateless: every request names
its client, and may carry credentials the client lends for that message; they
ride on the message said in the session, for whichever peer answers it. No
peer is added per client: messages are told apart by their ids.
"""

import asyncio
import base64
import hmac
import logging
import mimetypes
import re
import secrets
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

import mcp_types as types
from mcp.server.lowlevel.server import Server

from chatinho.chat_hooks import (
    HookAnswer,
    HookCommands,
    HookInvoke,
    HookListen,
    HookLocate,
    HookPeers,
    HookSay,
    Commands,
    Invoke,
    Locate,
    Peers,
    Say,
    declares,
    frontend,
    name_of,
    require,
)
from chatinho.chat_message import LOCAL, Attachment, ChatMessage, MessageID, Reply, ReplyStatus, Secret

logger = logging.getLogger(__name__)

#: Every result a call can end in; exactly one per call.
STATUSES : Tuple[str, ...] = ("answered", "asked", "error", "timeout")

#: Where a client puts the credentials it lends, in a request's ``_meta``, and
#: the capability extension a server declares the ones it accepts under.
CREDENTIALS_KEY : str = "chatinho/credentials"

#: How long a message may wait for its reply when nobody says otherwise, in seconds.
DEFAULT_DEADLINE : float = 120.0

_LINK = re.compile(r"\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")

#: What a peer is told when it asks the person this frontend stands in for.
_NOBODY_HERE = "Nobody is at this session's terminal: it is served over MCP"


@dataclass(eq=False)
class _Message:
    """One client's message in flight, from its ``say`` or ``ask`` call to its one result."""

    token       : str
    client      : str
    asker       : Tuple[str, str]
    deadline    : float
    seconds     : float
    credentials : Dict[str, Secret]
    reply       : "asyncio.Future[ChatMessage]"
    msg_id      : Optional[MessageID] = None
    room        : bool = False
    closed      : bool = False


_TEXT     = {"type": "string", "description": "What to say."}
_DEADLINE = {"type": "integer", "minimum": 1, "description": "How long to wait, in ms."}

_TOOLS = [
    types.Tool(
        name="say",
        description=(
            "Say something in this chatinho session, and get the first reply to it. When one peer "
            "answers in the session, it is asked of that peer; when several do, it is said to the room. "
            "The result is exactly one of: answered, asked (a question back to you), error or timeout."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "text"        : _TEXT,
                "asker"       : {"type": "string", "description": "Who says it, for follow-ups."},
                "deadline_ms" : _DEADLINE,
            },
            "required": ["text"],
        },
    ),
    types.Tool(
        name="ask",
        description=(
            "Ask one peer of this session, by name (see peers), and get its answer. The result is exactly "
            "one of: answered, asked (a question back to you), error or timeout."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "peer"        : {"type": "string", "description": "The peer's name."},
                "text"        : _TEXT,
                "deadline_ms" : _DEADLINE,
            },
            "required": ["peer", "text"],
        },
    ),
    types.Tool(
        name="peers",
        description="Lists the peers in this session, and whether each one answers what it is asked.",
        input_schema={"type": "object", "properties": {}},
    ),
    types.Tool(
        name="tools",
        description="Lists this session's tools (its slash commands), each with what it does.",
        input_schema={"type": "object", "properties": {}},
    ),
    types.Tool(
        name="run",
        description="Runs one of this session's tools (see tools) and returns what it answered.",
        input_schema={
            "type": "object",
            "properties": {
                "name"        : {"type": "string", "description": "The tool's name, without the slash."},
                "args"        : {"type": "string", "description": "Its arguments, as typed after its name."},
                "deadline_ms" : _DEADLINE,
            },
            "required": ["name"],
        },
    ),
]


@frontend("master")
@require(HookSay)
@require(HookListen)
@require(HookAnswer)
@require(HookPeers)
@require(HookCommands)
@require(HookInvoke)
@require(HookLocate)
class McpFrontend:
    """Bridges MCP clients into a session, in place of a terminal.

    Args:
        name: Its name in the session, and the server's name; ``master`` by default.
        token: The bearer token every request must carry; required.
        host: Where the server listens.
        port: The server's port.
        deadline: How long a message may wait for its reply when its client
            does not say, in seconds.
        credentials: The credentials the session's peers may use, by name, each
            with a short description; announced at discovery. Others are dropped.

    Raises:
        ValueError: No token, or a non-positive deadline.
    """

    say      : Say
    peers    : Peers
    commands : Commands
    invoke   : Invoke
    locate   : Locate

    def __init__(
        self,
        name        : str = "master",
        *,
        token       : str,
        host        : str = "127.0.0.1",
        port        : int = 8000,
        deadline    : float = DEFAULT_DEADLINE,
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
            self.server.extensions[CREDENTIALS_KEY] = dict(self.credentials)
        #: Messages waiting for their reply, by the id the frontend said them under.
        self._open : Dict[MessageID, _Message] = {}
        #: Each asker's last reply in the room, so its next message there replies to it.
        self._last_heard : Dict[Tuple[str, str], MessageID] = {}
        self._http : Any = None

    # === Being peer zero ============================================================

    async def answer(self, msg: ChatMessage) -> Optional[Reply]:
        """A peer asked the person, and there is none; a reply to what it said is only heard."""
        if msg.reply_to is not None:
            return None
        return Reply(_NOBODY_HERE, status=ReplyStatus.ERROR)

    async def listen(self, msg: ChatMessage) -> None:
        """Hands the first reply to a client's message back to that client."""
        if msg.reply_to is None:
            return
        open_ = self._open.get(msg.reply_to)
        if open_ is not None and not open_.reply.done():
            open_.reply.set_result(msg)

    async def serve(self) -> None:
        """Serves MCP over HTTP until the server stops, which ends the chat."""
        import uvicorn
        app    = _BearerOnly(self.server.streamable_http_app(host=self.host), self._token)
        config = uvicorn.Config(app, host=self.host, port=self.port, log_level="warning")
        self._http = uvicorn.Server(config)
        await self._http.serve()

    def shutdown(self) -> None:
        """Stops the HTTP server and lets go of every message still waiting."""
        if self._http is not None:
            self._http.should_exit = True
        for message in list(self._open.values()):
            self._close(message)

    # === MCP ========================================================================

    async def _list_tools(self, ctx: Any, params: Any) -> types.ListToolsResult:
        return types.ListToolsResult(tools=list(_TOOLS))

    async def _call_tool(self, ctx: Any, params: types.CallToolRequestParams) -> Any:
        meta   = dict(ctx.meta or {})
        info   = meta.get(types.CLIENT_INFO_META_KEY) or {}
        client = _safe_name(info.get("name") if isinstance(info, dict) else None, "client")
        args   = params.arguments or {}
        deadline = args.get("deadline_ms")
        seconds  = deadline / 1000.0 if isinstance(deadline, int) and deadline > 0 else self.deadline
        try:
            if params.name == "peers":
                return self._list_peers()
            if params.name == "tools":
                return self._list_commands()
            if params.name == "run":
                return await self._run(args.get("name"), args.get("args"), seconds)
            if params.name not in ("say", "ask"):
                return _result("error", "No tool named %r; this session takes %s"
                               % (params.name, ", ".join(tool.name for tool in _TOOLS)))
            text = args.get("text")
            if not isinstance(text, str) or not text.strip():
                return _result("error", "%s needs a text" % params.name)
            if params.name == "ask":
                message = await self._ask(client, args.get("peer"), text, seconds, meta)
            else:
                message = await self._forward(client, args.get("asker"), text, seconds, meta)
            if isinstance(message, types.CallToolResult):
                return message
            try:
                return await self._wait(message)
            finally:
                self._close(message)          # however the call ended, even cancelled
        except Exception as exc:
            logger.error("%s failed for %s", params.name, client, exc_info=True)
            return _result("error", "%s failed: %s" % (params.name, type(exc).__name__))

    # === The roster and the tools ===================================================

    def _list_peers(self) -> types.CallToolResult:
        """Everyone in the session but the frontend, by name, and whether each answers."""
        found = [{"name": name_of(who), "answers": declares(who, HookAnswer)}
                 for at, who in sorted(self.peers().items()) if at != LOCAL]
        lines = ["%s%s" % (peer["name"], "" if peer["answers"] else " (does not answer)") for peer in found]
        return _result("answered", "\n".join(lines) or "No peers.", peers=found)

    def _list_commands(self) -> types.CallToolResult:
        """The session's tools, by name, each with its description."""
        found = [{"name": name, "description": str(getattr(cmd, "description", "") or "")}
                 for name, cmd in sorted(self.commands().items())]
        lines = ["/%s - %s" % (tool["name"], tool["description"]) for tool in found]
        return _result("answered", "\n".join(lines) or "No tools.", tools=found)

    async def _run(self, name: Any, args: Any, seconds: float) -> types.CallToolResult:
        """Runs one of the session's tools, within the deadline."""
        if not isinstance(name, str) or name.lstrip("/") not in self.commands():
            return _result("error", "No tool named %r in this session" % (name,))
        name = name.lstrip("/")
        try:
            said = await asyncio.wait_for(self.invoke(name, args if isinstance(args, str) else ""), seconds)
        except asyncio.TimeoutError:
            return _result("timeout", "/%s did not answer within %g seconds" % (name, seconds))
        return _result("answered", said or "")

    # === One message ================================================================

    async def _ask(
        self, client: str, peer: Any, text: str, seconds: float, meta: Dict[str, Any],
    ) -> Any:
        """Asks *text* of the peer named *peer* for *client*; an error result if it cannot answer."""
        named = [(at, who) for at, who in sorted(self.peers().items())
                 if at != LOCAL and isinstance(peer, str) and name_of(who) == peer]
        if not named:
            return _result("error", "No peer named %r in this session" % (peer,))
        if len(named) > 1:
            return _result("error", "Several peers are named %r; ask with say instead" % peer)
        at, who = named[0]
        if not declares(who, HookAnswer):
            return _result("error", "%s does not answer what it is asked" % peer)
        message = self._message(client, "", seconds, meta)
        message.msg_id = await self.say(text, to=at, credentials=message.credentials)
        self._open[message.msg_id] = message
        return message

    async def _forward(
        self, client: str, asker: Any, text: str, seconds: float, meta: Dict[str, Any],
    ) -> Any:
        """Says *text* in the session for *client*; an error result if nobody could reply."""
        answering = self._answering()
        if not answering:
            return _result("error", "No peer in this session can answer")
        room = len(answering) > 1
        if room and not any(declares(who, HookListen) for _, who in answering):
            return _result(
                "error", "Several peers could answer and none listens to the room; a peer router is needed")

        message      = self._message(client, asker, seconds, meta)
        message.room = room
        # In the room, a follow-up replies to the asker's last reply; to a lone
        # peer it must not be a reply, or the session would not ask it.
        reply_to       = self._last_heard.get(message.asker) if room else None
        message.msg_id = await self.say(text, reply_to=reply_to, credentials=message.credentials)
        self._open[message.msg_id] = message
        return message

    async def _wait(self, message: _Message) -> types.CallToolResult:
        """Waits for the first reply or the deadline, whichever comes first."""
        remaining = message.deadline - asyncio.get_running_loop().time()
        if remaining > 0:
            await asyncio.wait({message.reply}, timeout=remaining)
        if not message.reply.done():
            return _result("timeout", "No reply within %g seconds" % message.seconds)
        reply = message.reply.result()
        if message.room:
            self._last_heard[message.asker] = reply.id
        attachments = await self._attachments_of(reply.id, reply.text)
        return _result(ReplyStatus(reply.status).value, reply.text, attachments, str(reply.id))

    def _message(self, client: str, asker: Any, seconds: float, meta: Dict[str, Any]) -> _Message:
        """A new message in flight for *client*, with its deadline and the credentials lent with it."""
        loop = asyncio.get_running_loop()
        return _Message(
            token       = secrets.token_urlsafe(18),
            client      = client,
            asker       = (client, _safe_name(asker, "")),
            deadline    = loop.time() + seconds,
            seconds     = seconds,
            credentials = self._lent(meta),
            reply       = loop.create_future(),
        )

    def _close(self, message: _Message) -> None:
        """Lets go of everything a message held: its wait and its credentials."""
        if message.closed:
            return
        message.closed = True
        if message.msg_id is not None:
            self._open.pop(message.msg_id, None)
        if not message.reply.done():
            message.reply.cancel()
        message.credentials.clear()

    # === Helpers ====================================================================

    def _answering(self) -> List[Tuple[int, Any]]:
        """The peers that can answer: everyone but the frontend that declares HookAnswer."""
        return [(at, who) for at, who in sorted(self.peers().items())
                if at != LOCAL and declares(who, HookAnswer)]

    def _lent(self, meta: Dict[str, Any]) -> Dict[str, Secret]:
        """The declared credentials lent with a message, wrapped so they never show."""
        lent = meta.get(CREDENTIALS_KEY)
        if not isinstance(lent, dict):
            return {}
        return {name: Secret(value) for name, value in lent.items()
                if name in self.credentials and isinstance(value, str)}

    async def _attachments_of(self, msg_id: MessageID, text: str) -> List[Attachment]:
        """What a reply attached: each name it links to that the backend can read back."""
        found: List[Attachment] = []
        for name in _linked_names(text):
            data = _read_link(await self.locate(msg_id, name))
            if data is not None:
                found.append(Attachment(name, _media_type_of(name), data))
        return found


# === What goes back to the client ================================================

def _result(
    status      : str,
    text        : str,
    attachments : Sequence[Attachment] = (),
    msg_id      : Optional[str] = None,
    **listed    : Any,
) -> types.CallToolResult:
    """Builds the result of one tool call.

    The structured content is what a chatinho client reads; the text block is
    for clients that only read text. ``error`` and ``timeout`` are tool errors.

    Args:
        status: One of :data:`STATUSES`.
        text: What to say.
        attachments: What the answer attached.
        msg_id: The reply's message id in this session, when a reply arrived.
        **listed: What a listing lists, under its own key (``peers``, ``tools``).

    Returns:
        types.CallToolResult: Ready to return from ``tools/call``.

    Raises:
        ValueError: *status* is not one of :data:`STATUSES`.
    """
    if status not in STATUSES:
        raise ValueError("A result's status is one of %s, got %r" % (", ".join(STATUSES), status))
    shown = text if status == "answered" else "[%s] %s" % (status, text)
    return types.CallToolResult(
        content=[types.TextContent(text=shown)],
        structured_content={
            "status"      : status,
            "text"        : text,
            "attachments" : [_encode(item) for item in attachments],
            "msg_id"      : msg_id,
            **listed,
        },
        is_error=status in ("error", "timeout"),
    )


def _safe_name(raw: Any, default: str) -> str:
    """A name that can stand in a peer path: non-empty, with no ``/``.

    Args:
        raw: What the other side called itself; anything.
        default: What to use when *raw* gives nothing usable.
    """
    if not isinstance(raw, str):
        return default
    name = " ".join(raw.replace("/", "-").split())
    return name or default


def _linked_names(text: str) -> List[str]:
    """The relative link targets in a Markdown *text*, in order, each once.

    In chatinho a message links its attachments by name — ``[chart](chart.svg)``
    — and that is the only list of them there is. Absolute URLs, paths and
    anchors are not attachments.
    """
    names: List[str] = []
    for target in _LINK.findall(text or ""):
        if ":" in target or target.startswith(("/", "#")):
            continue
        name = unquote(target)
        if name not in names:
            names.append(name)
    return names


def _read_link(url: Optional[str]) -> Optional[bytes]:
    """The bytes behind a ``file://`` link, or None for anything else or nothing there."""
    if not url:
        return None
    parsed = urlparse(url)
    if parsed.scheme != "file":
        return None
    try:
        with open(url2pathname(parsed.path), "rb") as handle:
            return handle.read()
    except OSError:
        return None


def _media_type_of(name: str) -> str:
    """The media type a file called *name* most likely holds."""
    return mimetypes.guess_type(name)[0] or "application/octet-stream"


def _encode(item: Attachment) -> Dict[str, str]:
    """An attachment as JSON: its name, media type and base64 content."""
    return {
        "name"       : item.name,
        "media_type" : item.media_type,
        "data_b64"   : base64.b64encode(item.data).decode("ascii"),
    }


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
