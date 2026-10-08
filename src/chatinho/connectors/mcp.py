"""A peer that puts questions to another chatinho session over MCP.

:class:`McpConnector` is an ordinary connector: it appears in the chat under a
name it chooses (``@lab``), and a message addressed to it — ``@lab will it
rain?`` — is said in the remote session through its ``say`` tool, and the
first reply to it comes back: exactly one reply for every such message.

It is a FastMCP client and speaks the modern MCP protocol (2026-07-28). When a
remote peer needs an LLM, the connector can lend it a credential for that one
question — out of band, only one the server declared, and only over HTTPS or
to this machine. Without ``delegate``, no key ever leaves this machine.
"""

import ipaddress
import logging
from typing import Any, Callable, Dict, Mapping, Optional, Union
from urllib.parse import urlparse

import mcp_types as types
from mcp_types.version import MODERN_PROTOCOL_VERSIONS

from chatinho.chat_hooks import (
    HookAnswer,
    HookListen,
    HookPeers,
    HookSay,
    Peers,
    Say,
    connector,
    name_of,
    require,
)
from chatinho.chat_message import TOOL, ChatMessage, Reply, ReplyStatus
from chatinho.helpers.mcp import CREDENTIALS_KEY, decode, safe_name

logger = logging.getLogger(__name__)


# === What comes back from the server ==============================================

def _reply_from(res: types.CallToolResult, name: str) -> Reply:
    """The local reply for what ``McpFrontend`` wrote, or the best of a plain result.

    ``answered`` keeps the text and attachments; ``asked`` becomes a question
    from the remote session; ``error`` becomes a short error.
    A server that is not a chatinho session answers with text alone: that is
    answered, or an error when the result is marked as one.
    """
    data = res.structured_content
    if isinstance(data, dict) and data.get("status") in {status.value for status in ReplyStatus}:
        status = data["status"]
        text   = str(data.get("text", ""))
    else:
        status = "error" if res.is_error else "answered"
        text   = "\n".join(block.text for block in res.content if isinstance(block, types.TextContent))
        data   = {}
    if status == "answered":
        return Reply(text, tuple(decode(item) for item in data.get("attachments") or ()))
    if status == "asked":
        return Reply("%s asks: %s" % (name, text), status=ReplyStatus.ASKED)
    return Reply("%s: %s — %s" % (name, status, text), status=ReplyStatus.ERROR)


@connector("mcp")
@require(HookListen)
@require(HookAnswer)
@require(HookSay)
@require(HookPeers)
class McpConnector:
    """Puts questions to a remote chatinho session.

    Give it exactly one server: an HTTP ``url`` with its bearer ``token``, or
    a ``server`` object (an in-process ``FastMCP`` server, such as an
    ``McpFrontend``'s ``.server``).

    Args:
        url: The Streamable HTTP endpoint, e.g. ``https://lab.example/mcp``.
        token: The bearer token the server requires; needed with *url*.
        server: An in-process server, for tests and embedding.
        name: Its name in the chat, and the client name the server sees; the
            server's name when left out.
        delegate: Credentials to lend, by name: a value, or a function returning
            one for each question. Only the ones the server declares are sent,
            and only over HTTPS or to this machine.

    Raises:
        ValueError: Not exactly one server, or a *url* without a *token*.
    """

    say   : Say
    peers : Peers

    def __init__(
        self,
        *,
        url         : Optional[str] = None,
        token       : Optional[str] = None,
        server      : Any = None,
        name        : Optional[str] = None,
        delegate    : Optional[Mapping[str, Union[str, Callable[[], str]]]] = None,
    ) -> None:
        if (url is None) == (server is None):
            raise ValueError("Give exactly one of url or server")
        if url is not None and not token:
            raise ValueError("An HTTP server needs its bearer token")
        self._url        = url
        self._token      = token
        self._server     = server
        self._named      = name is not None
        self.name        = safe_name(name, "mcp") if name is not None else "mcp"
        self._delegate   = dict(delegate or {})
        self._client     : Any = self._make_client()

    # === Lifecycle ==================================================================

    async def initialize(self) -> None:
        """Takes the server's name when none was given.

        A server that cannot be reached is not fatal: the chat goes on, and the
        next question tries again and answers that it could not.
        """
        if self._named:
            return
        try:
            async with self._client as client:
                found = client.server_info
        except Exception as exc:
            logger.warning("%s could not reach its server: %s", self.name, exc)
            return
        if found is not None:
            self.name    = safe_name(found.name, self.name)
            self._named  = True
            self._client = self._make_client()      # so the server sees the real name

    # === Being addressed ============================================================

    async def listen(self, msg: ChatMessage) -> None:
        """Takes a message said to the room that starts with ``@<its name>``."""
        if not msg.is_broadcast or msg.frm == TOOL:
            return
        text = self._addressed(msg.text)
        if text is None:
            return
        reply = await self._say_remote(text, self._asker(msg.frm))
        await self.say(reply.text, reply_to=msg.id, attachments=reply.attachments)

    async def answer(self, msg: ChatMessage) -> Reply:
        """A question asked to it directly; the ``@<its name>`` prefix is optional."""
        text = self._addressed(msg.text)
        return await self._say_remote(text if text is not None else msg.text, self._asker(msg.frm))

    def _addressed(self, text: str) -> Optional[str]:
        """The rest of *text* when it starts with ``@<name>`` and whitespace, else None."""
        prefix = "@" + self.name
        stripped = text.lstrip()
        if not stripped.startswith(prefix):
            return None
        rest = stripped[len(prefix):]
        if not rest or not rest[0].isspace():
            return None
        return rest.strip() or None

    def _asker(self, frm: int) -> str:
        who = self.peers().get(frm)
        return name_of(who) if who is not None else "peer-%d" % frm

    # === One question ===============================================================

    async def _say_remote(self, text: str, asker: str) -> Reply:
        """Asks the remote session, and turns whatever happens into one reply."""
        if self._delegate and not self._may_delegate():
            return Reply("%s: lending credentials needs HTTPS; nothing was sent" % self.name,
                         status=ReplyStatus.ERROR)
        args = {"text": text, "asker": asker}
        try:
            async with self._client as client:
                if client.protocol_version not in MODERN_PROTOCOL_VERSIONS:
                    raise RuntimeError("The server speaks only the handshake-era MCP protocol")
                result = await client.call_tool("say", args, meta=self._lending(client), raise_on_error=False)
        except Exception as exc:
            logger.warning("%s could not ask its server: %r", self.name, exc)
            return Reply("%s: could not reach the remote session (%s)" % (self.name, type(exc).__name__),
                         status=ReplyStatus.ERROR)
        return _reply_from(result, self.name)

    # === Lending ====================================================================

    def _may_delegate(self) -> bool:
        """Credentials go over HTTPS, or to this machine — never over plain HTTP elsewhere."""
        if self._url is None:
            return True
        parsed = urlparse(self._url)
        if parsed.scheme == "https":
            return True
        host = parsed.hostname or ""
        if host == "localhost":
            return True
        try:
            return ipaddress.ip_address(host).is_loopback
        except ValueError:
            return False

    def _lending(self, client: Any) -> Optional[Dict[str, Any]]:
        """The ``_meta`` for one question: the configured credentials the server declared."""
        if not self._delegate:
            return None
        found    = client.server_capabilities
        declared = ((found.extensions or {}).get(CREDENTIALS_KEY) or {}) if found else {}
        lent     = {name: (value() if callable(value) else value)
                    for name, value in self._delegate.items() if name in declared}
        return {CREDENTIALS_KEY: lent} if lent else None

    # === The client ===================================================================

    def _make_client(self) -> Any:
        from fastmcp import Client
        return Client(
            self._server if self._server is not None else str(self._url),
            auth        = self._token if self._server is None else None,
            client_info = types.Implementation(name=self.name, version="chatinho"),
        )
