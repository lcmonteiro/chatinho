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
Streamable HTTP, with a bearer token on every request. The protocol is
stateless: every request names its client, and may carry credentials the client
lends for that message; they ride on the message said in the session, for
whichever peer answers it. No peer is added per client: messages are told apart
by their ids.
"""

import asyncio
import hmac
import logging
import re
from dataclasses import dataclass
from typing import Annotated, Any, Dict, List, Optional, Sequence, Tuple
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

import mcp_types as types
from fastmcp import Context, FastMCP
from fastmcp.server.auth import AccessToken, TokenVerifier
from fastmcp.server.extensions import ServerExtension
from fastmcp.tools.base import ToolResult
from pydantic import BaseModel, Field

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
from chatinho.helpers.mcp import CREDENTIALS_KEY, encode, media_type_of, safe_name

logger = logging.getLogger(__name__)

_LINK = re.compile(r"\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")

#: What a peer is told when it asks the person this frontend stands in for.
_NOBODY_HERE = "Nobody is at this session's terminal: it is served over MCP"


@dataclass(eq=False)
class _Message:
    """One client's message in flight, from its ``say`` or ``ask`` call to its one result."""

    client      : str
    asker       : Tuple[str, str]
    credentials : Dict[str, Secret]
    reply       : "asyncio.Future[ChatMessage]"
    msg_id      : Optional[MessageID] = None
    room        : bool = False
    closed      : bool = False


_Text = Annotated[str, Field(description="What to say.")]


class PeerInfo(BaseModel):
    """One peer in the session, as ``peers`` lists it."""

    name    : str
    answers : bool


class ToolInfo(BaseModel):
    """One of the session's tools (a slash command), as ``tools`` lists it."""

    name        : str
    description : str


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
        credentials: The credentials the session's peers may use, by name, each
            with a short description; announced at discovery. Others are dropped.

    Raises:
        ValueError: No token.
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
        credentials : Optional[Dict[str, str]] = None,
    ) -> None:
        if not token:
            raise ValueError("McpFrontend needs a bearer token")
        self.name        = name
        self.host        = host
        self.port        = port
        self.credentials : Dict[str, str] = dict(credentials or {})
        self._token      = token
        #: The MCP server itself; an in-process client can connect to it directly.
        self.server = FastMCP(name, auth=_OneToken(token))
        self.server.tool(self._say,   name="say")
        self.server.tool(self._ask,   name="ask")
        self.server.tool(self._peers, name="peers")
        self.server.tool(self._tools, name="tools")
        self.server.tool(self._run,   name="run")
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

    # === The tools ==================================================================

    async def _say(
        self,
        text        : _Text,
        ctx         : Context,
        asker       : Annotated[Optional[str], Field(description="Who says it, for follow-ups.")] = None,
    ) -> ToolResult:
        """Say something in this chatinho session, and get the first reply to it.

        When one peer answers in the session, it is asked of that peer; when
        several do, it is said to the room. The result is exactly one of:
        answered, asked (a question back to you) or error.
        """
        def send(client: str, meta: Dict[str, Any]) -> Any:
            return self._forward(client, asker, text, meta)
        return await self._bridged("say", ctx, text, send)

    async def _ask(
        self,
        peer        : Annotated[str, Field(description="The peer's name.")],
        text        : _Text,
        ctx         : Context,
    ) -> ToolResult:
        """Ask one peer of this session, by name (see peers), and get its answer.

        The result is exactly one of: answered, asked (a question back to you)
        or error.
        """
        def send(client: str, meta: Dict[str, Any]) -> Any:
            return self._asked(client, peer, text, meta)
        return await self._bridged("ask", ctx, text, send)

    async def _peers(self) -> List[PeerInfo]:
        """Lists the peers in this session, and whether each one answers what it is asked."""
        return [PeerInfo(name=name_of(who), answers=declares(who, HookAnswer))
                for at, who in sorted(self.peers().items()) if at != LOCAL]

    async def _tools(self) -> List[ToolInfo]:
        """Lists this session's tools (its slash commands), each with what it does."""
        return [ToolInfo(name=name, description=str(getattr(cmd, "description", "") or ""))
                for name, cmd in sorted(self.commands().items())]

    async def _run(
        self,
        name        : Annotated[str, Field(description="The tool's name, without the slash.")],
        args        : Annotated[str, Field(description="Its arguments, as typed after its name.")] = "",
    ) -> ToolResult:
        """Runs one of this session's tools (see tools) and returns what it answered."""
        name = name.lstrip("/")
        if name not in self.commands():
            return _result(ReplyStatus.ERROR, "No tool named %r in this session" % name)
        try:
            said = await self.invoke(name, args)
        except Exception as exc:
            logger.error("run /%s failed", name, exc_info=True)
            return _result(ReplyStatus.ERROR, "/%s failed: %s" % (name, type(exc).__name__))
        return _result(ReplyStatus.ANSWERED, said or "")

    # === One call ===================================================================

    async def _bridged(self, tool: str, ctx: Context, text: str, send: Any) -> ToolResult:
        """Sends one message for a ``say`` or ``ask`` call, and waits for its one result."""
        meta   = dict(ctx.request_context.meta or {}) if ctx.request_context is not None else {}
        info   = meta.get(types.CLIENT_INFO_META_KEY) or {}
        client = safe_name(info.get("name") if isinstance(info, dict) else None, "client")
        if not text.strip():
            return _result(ReplyStatus.ERROR, "%s needs a text" % tool)
        try:
            message = await send(client, meta)
            if isinstance(message, ToolResult):
                return message
            try:
                return await self._wait(message)
            finally:
                self._close(message)          # however the call ended, even cancelled
        except Exception as exc:
            logger.error("%s failed for %s", tool, client, exc_info=True)
            return _result(ReplyStatus.ERROR, "%s failed: %s" % (tool, type(exc).__name__))

    # === One message ================================================================

    async def _asked(
        self, client: str, peer: str, text: str, meta: Dict[str, Any],
    ) -> Any:
        """Asks *text* of the peer named *peer* for *client*; an error result if it cannot answer."""
        named = [(at, who) for at, who in sorted(self.peers().items())
                 if at != LOCAL and name_of(who) == peer]
        if not named:
            return _result(ReplyStatus.ERROR, "No peer named %r in this session" % (peer,))
        if len(named) > 1:
            return _result(ReplyStatus.ERROR, "Several peers are named %r; ask with say instead" % peer)
        at, who = named[0]
        if not declares(who, HookAnswer):
            return _result(ReplyStatus.ERROR, "%s does not answer what it is asked" % peer)
        message = self._message(client, "", meta)
        message.msg_id = await self.say(text, to=at, credentials=message.credentials)
        self._open[message.msg_id] = message
        return message

    async def _forward(
        self, client: str, asker: Any, text: str, meta: Dict[str, Any],
    ) -> Any:
        """Says *text* in the session for *client*; an error result if nobody could reply."""
        answering = self._answering()
        if not answering:
            return _result(ReplyStatus.ERROR, "No peer in this session can answer")
        room = len(answering) > 1
        if room and not any(declares(who, HookListen) for _, who in answering):
            return _result(ReplyStatus.ERROR,
                           "Several peers could answer and none listens to the room; a peer router is needed")

        message      = self._message(client, asker, meta)
        message.room = room
        # In the room, a follow-up replies to the asker's last reply; to a lone
        # peer it must not be a reply, or the session would not ask it.
        reply_to       = self._last_heard.get(message.asker) if room else None
        message.msg_id = await self.say(text, reply_to=reply_to, credentials=message.credentials)
        self._open[message.msg_id] = message
        return message

    async def _wait(self, message: _Message) -> ToolResult:
        """Waits for the first reply to *message*."""
        reply = await message.reply
        if message.room:
            self._last_heard[message.asker] = reply.id
        attachments = await self._attachments_of(reply.id, reply.text)
        return _result(ReplyStatus(reply.status), reply.text, attachments, str(reply.id))

    def _message(self, client: str, asker: Any, meta: Dict[str, Any]) -> _Message:
        """A new message in flight for *client*, with the credentials lent with it."""
        return _Message(
            client      = client,
            asker       = (client, safe_name(asker, "")),
            credentials = self._lent(meta),
            reply       = asyncio.get_running_loop().create_future(),
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
                found.append(Attachment(name, media_type_of(name), data))
        return found


# === What goes back to the client ================================================

def _result(
    status      : ReplyStatus,
    text        : str,
    attachments : Sequence[Attachment] = (),
    msg_id      : Optional[str] = None,
) -> ToolResult:
    """Builds the result of one tool call.

    The structured content is what a chatinho client reads; the text block is
    for clients that only read text. ``error`` is a tool error.

    Args:
        status: How the reply describes itself.
        text: What to say.
        attachments: What the answer attached.
        msg_id: The reply's message id in this session, when a reply arrived.

    Returns:
        ToolResult: Ready to return from a tool.
    """
    shown = text if status is ReplyStatus.ANSWERED else "[%s] %s" % (status.value, text)
    return ToolResult(
        content=shown,
        structured_content={
            "status"      : status.value,
            "text"        : text,
            "attachments" : [encode(item) for item in attachments],
            "msg_id"      : msg_id,
        },
        is_error=status is ReplyStatus.ERROR,
    )


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
