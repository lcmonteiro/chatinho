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

It is built on FastMCP and speaks the modern MCP protocol (2026-07-28) over
Streamable HTTP, with a bearer token on every request. The protocol is stateless: every request names
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
from typing import Annotated, Any, Dict, List, Optional, Sequence, Tuple
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

import mcp_types as types
from fastmcp import Context, FastMCP
from fastmcp.server.auth import AccessToken, TokenVerifier
from fastmcp.server.extensions import ServerExtension
from fastmcp.tools.base import ToolResult
from pydantic import Field

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


_Text     = Annotated[str, Field(description="What to say.")]
_Deadline = Annotated[Optional[int], Field(ge=1, description="How long to wait, in ms.")]

#: The tools, by name, with what each one tells a client about itself.
_TOOLS : Dict[str, str] = {
    "say"   : ("Say something in this chatinho session, and get the first reply to it. When one peer "
               "answers in the session, it is asked of that peer; when several do, it is said to the room. "
               "The result is exactly one of: answered, asked (a question back to you), error or timeout."),
    "ask"   : ("Ask one peer of this session, by name (see peers), and get its answer. The result is exactly "
               "one of: answered, asked (a question back to you), error or timeout."),
    "peers" : "Lists the peers in this session, and whether each one answers what it is asked.",
    "tools" : "Lists this session's tools (its slash commands), each with what it does.",
    "run"   : "Runs one of this session's tools (see tools) and returns what it answered.",
}


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
        self.server = FastMCP(name, auth=_OneToken(token))
        for tool in (self._say, self._ask, self._peers, self._tools, self._run):
            name_ = tool.__name__.lstrip("_")
            self.server.tool(tool, name=name_, description=_TOOLS[name_])
        if self.credentials:
            self.server.add_extension(_Credentials(self.credentials))
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
        config = uvicorn.Config(self.server.http_app(), host=self.host, port=self.port, log_level="warning")
        self._http = uvicorn.Server(config)
        await self._http.serve()

    def shutdown(self) -> None:
        """Stops the HTTP server and lets go of every message still waiting."""
        if self._http is not None:
            self._http.should_exit = True
        for message in list(self._open.values()):
            self._close(message)

    # === MCP ========================================================================

    async def _say(
        self, text: _Text, ctx: Context,
        asker       : Annotated[Optional[str], Field(description="Who says it, for follow-ups.")] = None,
        deadline_ms : _Deadline = None,
    ) -> ToolResult:
        def send(client: str, seconds: float, meta: Dict[str, Any]) -> Any:
            return self._forward(client, asker, text, seconds, meta)
        return await self._bridged("say", ctx, text, deadline_ms, send)

    async def _ask(
        self,
        peer        : Annotated[str, Field(description="The peer's name.")],
        text        : _Text,
        ctx         : Context,
        deadline_ms : _Deadline = None,
    ) -> ToolResult:
        def send(client: str, seconds: float, meta: Dict[str, Any]) -> Any:
            return self._asked(client, peer, text, seconds, meta)
        return await self._bridged("ask", ctx, text, deadline_ms, send)

    async def _peers(self) -> ToolResult:
        """Everyone in the session but the frontend, by name, and whether each answers."""
        found = [{"name": name_of(who), "answers": declares(who, HookAnswer)}
                 for at, who in sorted(self.peers().items()) if at != LOCAL]
        lines = ["%s%s" % (peer["name"], "" if peer["answers"] else " (does not answer)") for peer in found]
        return _result("answered", "\n".join(lines) or "No peers.", peers=found)

    async def _tools(self) -> ToolResult:
        """The session's tools, by name, each with its description."""
        found = [{"name": name, "description": str(getattr(cmd, "description", "") or "")}
                 for name, cmd in sorted(self.commands().items())]
        lines = ["/%s - %s" % (tool["name"], tool["description"]) for tool in found]
        return _result("answered", "\n".join(lines) or "No tools.", tools=found)

    async def _run(
        self,
        name        : Annotated[str, Field(description="The tool's name, without the slash.")],
        args        : Annotated[str, Field(description="Its arguments, as typed after its name.")] = "",
        deadline_ms : _Deadline = None,
    ) -> ToolResult:
        """Runs one of the session's tools, within the deadline."""
        seconds = deadline_ms / 1000.0 if deadline_ms else self.deadline
        name    = name.lstrip("/")
        if name not in self.commands():
            return _result("error", "No tool named %r in this session" % name)
        try:
            said = await asyncio.wait_for(self.invoke(name, args), seconds)
        except asyncio.TimeoutError:
            return _result("timeout", "/%s did not answer within %g seconds" % (name, seconds))
        except Exception as exc:
            logger.error("run /%s failed", name, exc_info=True)
            return _result("error", "/%s failed: %s" % (name, type(exc).__name__))
        return _result("answered", said or "")

    async def _bridged(
        self, tool: str, ctx: Context, text: str, deadline_ms: Optional[int], send: Any,
    ) -> ToolResult:
        """Sends one message for a ``say`` or ``ask`` call, and waits for its one result."""
        meta    = dict(ctx.request_context.meta or {}) if ctx.request_context is not None else {}
        info    = meta.get(types.CLIENT_INFO_META_KEY) or {}
        client  = _safe_name(info.get("name") if isinstance(info, dict) else None, "client")
        seconds = deadline_ms / 1000.0 if deadline_ms else self.deadline
        if not text.strip():
            return _result("error", "%s needs a text" % tool)
        try:
            message = await send(client, seconds, meta)
            if isinstance(message, ToolResult):
                return message
            try:
                return await self._wait(message)
            finally:
                self._close(message)          # however the call ended, even cancelled
        except Exception as exc:
            logger.error("%s failed for %s", tool, client, exc_info=True)
            return _result("error", "%s failed: %s" % (tool, type(exc).__name__))

    # === One message ================================================================

    async def _asked(
        self, client: str, peer: str, text: str, seconds: float, meta: Dict[str, Any],
    ) -> Any:
        """Asks *text* of the peer named *peer* for *client*; an error result if it cannot answer."""
        named = [(at, who) for at, who in sorted(self.peers().items())
                 if at != LOCAL and name_of(who) == peer]
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

    async def _wait(self, message: _Message) -> ToolResult:
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
) -> ToolResult:
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
        ToolResult: Ready to return from a tool.

    Raises:
        ValueError: *status* is not one of :data:`STATUSES`.
    """
    if status not in STATUSES:
        raise ValueError("A result's status is one of %s, got %r" % (", ".join(STATUSES), status))
    shown = text if status == "answered" else "[%s] %s" % (status, text)
    return ToolResult(
        content=shown,
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


class _OneToken(TokenVerifier):
    """Lets in the requests that carry the one bearer token, compared in constant time."""

    def __init__(self, token: str) -> None:
        super().__init__()
        self._token = token.encode()

    async def verify_token(self, token: str) -> Optional[AccessToken]:
        if hmac.compare_digest(token.encode(), self._token):
            return AccessToken(token=token, client_id="client", scopes=[])
        return None


class _Credentials(ServerExtension):
    """The ``chatinho/credentials`` extension: the credentials a server accepts, announced at discovery."""

    def __init__(self, declared: Dict[str, str]) -> None:
        self.identifier = CREDENTIALS_KEY
        self.declared   = dict(declared)

    def settings(self) -> Dict[str, Any]:
        return dict(self.declared)
