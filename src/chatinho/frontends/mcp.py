"""A chatinho session served over MCP, in place of a terminal.

:class:`McpFrontend` is the session's peer zero, as a terminal would be, but
nobody types into it. Its tools are what a person at the terminal can do:

- ``ask``: ask one peer, by name, and get its answer.
- ``peers``: who is in the session, and which of them answer.
- ``tools``: the session's tools (its slash commands).
- ``invoke``: invoke one of them, and get what it answered.

It is built on FastMCP and speaks the modern MCP protocol (2026-07-28) over
Streamable HTTP, with a bearer token on every request. The protocol is
stateless: every request may carry credentials the client lends for that
question; they ride on the message asked in the session, for the peer that
answers it. No peer is added per client: questions are told apart by their ids.
"""

import asyncio
import hmac
import logging
import re
from dataclasses import dataclass
from typing import Annotated, Any, Dict, List, Optional
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.auth import AccessToken, TokenVerifier
from fastmcp.server.extensions import ServerExtension
from pydantic import BaseModel, Field

from chatinho.chat_hooks import HookAnswer, HookCommands, HookInvoke, HookListen, HookLocate, HookPeers
from chatinho.chat_hooks import HookSay
from chatinho.chat_hooks import Commands, Invoke, Locate, Peers, Say
from chatinho.chat_hooks import declares, frontend, name_of, require
from chatinho.chat_message import LOCAL, Attachment, ChatMessage, MessageID, ReplyStatus, Secret
from chatinho.helpers.mcp import CREDENTIALS_KEY, encode, media_type_of

logger = logging.getLogger(__name__)

_LINK = re.compile(r"\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")


@dataclass(eq=False)
class _Message:
    """One client's question in flight, from its ``ask`` call to its one result."""

    credentials : Dict[str, Secret]
    reply       : "asyncio.Future[ChatMessage]"
    msg_id      : Optional[MessageID] = None
    closed      : bool = False


_Text = Annotated[str, Field(description="What to say.")]


class Answer(BaseModel):
    """What ``ask`` and ``invoke`` return; a failure is a tool error instead."""

    status      : ReplyStatus = Field(description="answered, or asked: a question back to you.")
    text        : str
    #: Each attachment as ``{name, media_type, data_b64}``.
    attachments : List[Dict[str, str]] = Field(default_factory=list)
    msg_id      : Optional[str] = Field(default=None, description="The reply's message id in this session.")


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
        self.server.tool(self._ask,    name="ask")
        self.server.tool(self._peers,  name="peers")
        self.server.tool(self._tools,  name="tools")
        self.server.tool(self._invoke, name="invoke")
        if self.credentials:
            self.server.add_extension(_Credentials(self.credentials))
        #: Messages waiting for their reply, by the id the frontend said them under.
        self._open : Dict[MessageID, _Message] = {}
        self._serving  : Optional["asyncio.Task[Any]"] = None
        self._stopping : bool = False

    # === Being peer zero ============================================================

    async def listen(self, msg: ChatMessage) -> None:
        """Hands the first reply to a client's message back to that client."""
        if msg.reply_to is None:
            return
        open_ = self._open.get(msg.reply_to)
        if open_ is not None and not open_.reply.done():
            open_.reply.set_result(msg)

    async def serve(self) -> None:
        """Serves MCP over HTTP with FastMCP until it is shut down, which ends the chat."""
        self._serving = asyncio.current_task()
        try:
            await self.server.run_async(transport="http", host=self.host, port=self.port,
                                        show_banner=False, log_level="warning")
        except asyncio.CancelledError:
            if not self._stopping:
                raise

    def shutdown(self) -> None:
        """Stops the HTTP server and lets go of every message still waiting."""
        self._stopping = True
        if self._serving is not None and not self._serving.done():
            self._serving.cancel()
        for message in list(self._open.values()):
            self._close(message)

    # === The tools ==================================================================

    async def _ask(
        self,
        peer        : Annotated[str, Field(description="The peer's name.")],
        text        : _Text,
        ctx         : Context,
    ) -> Answer:
        """Ask one peer of this session, by name (see peers), and get its answer.

        The answer is answered or asked (a question back to you); a failure is a
        tool error.
        """
        return await self._wait(await self._asked(peer, text, _meta(ctx)))

    async def _peers(self) -> List[PeerInfo]:
        """Lists the peers in this session, and whether each one answers what it is asked."""
        return [PeerInfo(name=name_of(who), answers=declares(who, HookAnswer))
                for at, who in sorted(self.peers().items()) if at != LOCAL]

    async def _tools(self) -> List[ToolInfo]:
        """Lists this session's tools (its slash commands), each with what it does."""
        return [ToolInfo(name=name, description=str(getattr(cmd, "description", "") or ""))
                for name, cmd in sorted(self.commands().items())]

    async def _invoke(
        self,
        name        : Annotated[str, Field(description="The tool's name, as tools lists it.")],
        args        : Annotated[str, Field(description="Its arguments, as typed after its name.")] = "",
    ) -> Answer:
        """Runs one of this session's tools (see tools) and returns what it answered."""
        if name not in self.commands():
            raise ToolError("No tool named %r in this session" % name)
        return Answer(status=ReplyStatus.ANSWERED, text=await self.invoke(name, args) or "")

    # === One message ================================================================

    async def _asked(self, peer: str, text: str, meta: Dict[str, Any]) -> _Message:
        """Asks *text* of the peer named *peer*, with the credentials lent in *meta*."""
        named = [(at, who) for at, who in sorted(self.peers().items())
                 if at != LOCAL and name_of(who) == peer]
        if not named:
            raise ToolError("No peer named %r in this session" % (peer,))
        if len(named) > 1:
            raise ToolError("Several peers are named %r" % peer)
        at, who = named[0]
        if not declares(who, HookAnswer):
            raise ToolError("%s does not answer what it is asked" % peer)
        message = _Message(credentials=self._lent(meta), reply=asyncio.get_running_loop().create_future())
        message.msg_id = await self.say(text, to=at, credentials=message.credentials)
        self._open[message.msg_id] = message
        return message

    async def _wait(self, message: _Message) -> Answer:
        """Waits for the first reply to *message*, and lets go of it however the wait ends."""
        try:
            reply = await message.reply
        finally:
            self._close(message)
        if reply.status is ReplyStatus.ERROR:
            raise ToolError(reply.text)
        attachments = await self._attachments_of(reply.id, reply.text)
        return Answer(status=reply.status, text=reply.text, msg_id=str(reply.id),
                      attachments=[encode(item) for item in attachments])

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


# === Helpers ======================================================================

def _meta(ctx: Context) -> Dict[str, Any]:
    """The request's ``_meta``, where a client lends its credentials."""
    return dict(ctx.request_context.meta or {}) if ctx.request_context is not None else {}


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
