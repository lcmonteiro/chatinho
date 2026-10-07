"""A chatinho session served over MCP, in place of a terminal.

:class:`McpFrontend` is the session's peer zero, as a terminal would be, but
nobody types into it. It is a bridge with one tool, ``say``: what a client says
is said in the session by the frontend, and the first reply to it goes back to
that client. When one peer answers in the session, the session asks it of that
peer; when several do, it is said to the room.

It speaks the modern MCP protocol (2026-07-28) over Streamable HTTP, with a
bearer token on every request. The protocol is stateless: every request names
its client, and may carry credentials the client lends for that message. No
peer is added per client: messages are told apart by their ids.
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
    CredentialUnavailable,
    HookAnswer,
    HookListen,
    HookLocate,
    HookPeers,
    HookSay,
    HookServeCredential,
    Locate,
    Peers,
    Say,
    declares,
    frontend,
    require,
)
from chatinho.chat_message import LOCAL, Attachment, ChatMessage, MessageID, Reply, Secret
from chatinho import mcp_wire as wire

logger = logging.getLogger(__name__)

#: What a peer is told when it asks the person this frontend stands in for.
_NOBODY_HERE = "Nobody is at this session's terminal: it is served over MCP"


@dataclass(eq=False)
class _Message:
    """One client's message in flight, from its ``say`` call to its one result."""

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


_SAY = types.Tool(
    name="say",
    description=(
        "Say something in this chatinho session, and get the first reply to it. When one peer answers "
        "in the session, it is asked of that peer; when several do, it is said to the room. The result "
        "is exactly one of: answered, asked (a question back to you), error or timeout."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "text"        : {"type": "string", "description": "What to say."},
            "asker"       : {"type": "string", "description": "Who says it, to keep follow-ups together."},
            "deadline_ms" : {"type": "integer", "minimum": 1, "description": "How long to wait, in ms."},
        },
        "required": ["text"],
    },
)


@frontend("master")
@require(HookSay)
@require(HookListen)
@require(HookAnswer)
@require(HookPeers)
@require(HookLocate)
@require(HookServeCredential)
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
        return Reply(_NOBODY_HERE, status="error")

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

    # === Lending to whoever answers =================================================

    async def serve_credential(self, msg_id: MessageID, name: str) -> str:
        """The credential *name* lent with message *msg_id*, while it waits for its reply."""
        message = self._open.get(msg_id)
        if message is None or message.closed or name not in message.credentials:
            raise CredentialUnavailable("No credential %r was lent for %s" % (name, msg_id))
        return message.credentials[name].reveal()

    # === MCP ========================================================================

    async def _list_tools(self, ctx: Any, params: Any) -> types.ListToolsResult:
        return types.ListToolsResult(tools=[_SAY])

    async def _call_tool(self, ctx: Any, params: types.CallToolRequestParams) -> Any:
        if params.name != "say":
            return wire.result("error", "No tool named %r; this session only takes say" % params.name)
        meta   = dict(ctx.meta or {})
        info   = meta.get(types.CLIENT_INFO_META_KEY) or {}
        client = wire.safe_name(info.get("name") if isinstance(info, dict) else None, "client")
        args   = params.arguments or {}
        text   = args.get("text")
        if not isinstance(text, str) or not text.strip():
            return wire.result("error", "say needs a text")
        deadline = args.get("deadline_ms")
        seconds  = deadline / 1000.0 if isinstance(deadline, int) and deadline > 0 else self.deadline
        try:
            message = await self._forward(client, args.get("asker"), text, seconds, meta)
            if isinstance(message, types.CallToolResult):
                return message
            try:
                return await self._wait(message)
            finally:
                self._close(message)          # however the call ended, even cancelled
        except Exception as exc:
            logger.error("say failed for %s", client, exc_info=True)
            return wire.result("error", "say failed: %s" % type(exc).__name__)

    # === One message ================================================================

    async def _forward(
        self, client: str, asker: Any, text: str, seconds: float, meta: Dict[str, Any],
    ) -> Any:
        """Says *text* in the session for *client*; an error result if nobody could reply."""
        answering = self._answering()
        if not answering:
            return wire.result("error", "No peer in this session can answer")
        room = len(answering) > 1
        if room and not any(declares(who, HookListen) for _, who in answering):
            return wire.result(
                "error", "Several peers could answer and none listens to the room; a peer router is needed")

        loop    = asyncio.get_running_loop()
        message = _Message(
            token       = secrets.token_urlsafe(18),
            client      = client,
            asker       = (client, wire.safe_name(asker, "")),
            deadline    = loop.time() + seconds,
            seconds     = seconds,
            credentials = self._lent(meta),
            reply       = loop.create_future(),
            room        = room,
        )
        # In the room, a follow-up replies to the asker's last reply; to a lone
        # peer it must not be a reply, or the session would not ask it.
        reply_to       = self._last_heard.get(message.asker) if room else None
        message.msg_id = await self.say(text, reply_to=reply_to)
        self._open[message.msg_id] = message
        return message

    async def _wait(self, message: _Message) -> types.CallToolResult:
        """Waits for the first reply or the deadline, whichever comes first."""
        remaining = message.deadline - asyncio.get_running_loop().time()
        if remaining > 0:
            await asyncio.wait({message.reply}, timeout=remaining)
        if not message.reply.done():
            return wire.result("timeout", "No reply within %g seconds" % message.seconds)
        reply = message.reply.result()
        if message.room:
            self._last_heard[message.asker] = reply.id
        attachments = await self._attachments_of(reply.id, reply.text)
        return wire.result(reply.status, reply.text, attachments, str(reply.id))

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
        lent = meta.get(wire.CREDENTIALS_KEY)
        if not isinstance(lent, dict):
            return {}
        return {name: Secret(value) for name, value in lent.items()
                if name in self.credentials and isinstance(value, str)}

    async def _attachments_of(self, msg_id: MessageID, text: str) -> List[Attachment]:
        """What a reply attached: each name it links to that the backend can read back."""
        found: List[Attachment] = []
        for name in wire.linked_names(text):
            data = wire.read_link(await self.locate(msg_id, name))
            if data is not None:
                found.append(Attachment(name, wire.media_type_of(name), data))
        return found


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
