"""A peer that puts questions to another chatinho session over MCP.

:class:`McpConnector` is an ordinary connector: it appears in the chat under a
name it chooses (``lab``) and answers what it is asked. Each question is asked
of one remote peer through the remote session's ``ask`` tool — the ``peer``
given, or else the only remote peer that answers — and exactly one reply comes
back for every question.

It is a FastMCP client and speaks the modern MCP protocol (2026-07-28). When a
remote peer needs an LLM, the connector can lend it a credential for that one
question — out of band, and only one the server declared. Without ``delegate``,
no key ever leaves this machine; choosing a transport fit to carry one (HTTPS)
is up to whoever builds the system.
"""

import logging
from typing import Any, Callable, Dict, Mapping, Optional, Union

import mcp_types as types
from mcp_types.version import MODERN_PROTOCOL_VERSIONS

from chatinho.chat_hooks import HookAnswer
from chatinho.chat_hooks import connector, require
from chatinho.chat_message import ChatMessage, Reply, ReplyStatus
from chatinho.helpers.mcp import CREDENTIALS_KEY, decode

logger = logging.getLogger(__name__)


# === What comes back from the server ==============================================

def _reply_from(res: types.CallToolResult, name: str) -> Reply:
    """The local reply for what came back from the remote session.

    A tool error is an ``ERROR`` reply naming the remote session. Otherwise the
    status is the remote reply's own ``ReplyStatus``: ``ANSWERED`` keeps the text
    and attachments, ``ASKED`` is a question back from the remote session. A
    server that is not a chatinho session answers with text alone: ``ANSWERED``.
    """
    plain = "\n".join(block.text for block in res.content if isinstance(block, types.TextContent))
    if res.is_error:
        return Reply("%s: error — %s" % (name, plain), status=ReplyStatus.ERROR)
    data = res.structured_content if isinstance(res.structured_content, dict) else {}
    text = str(data.get("text", plain))
    if data.get("status") == ReplyStatus.ASKED:
        return Reply("%s asks: %s" % (name, text), status=ReplyStatus.ASKED)
    return Reply(text, tuple(decode(item) for item in data.get("attachments") or ()))


@connector("mcp")
@require(HookAnswer)
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
        peer: The remote peer to ask; the only remote peer that answers when
            left out.
        delegate: Credentials to lend, by name: a value, or a function returning
            one for each question. Only the ones the server declares are sent.

    Raises:
        ValueError: Not exactly one server, or a *url* without a *token*.
    """

    def __init__(
        self,
        *,
        url         : Optional[str] = None,
        token       : Optional[str] = None,
        server      : Any = None,
        name        : Optional[str] = None,
        peer        : Optional[str] = None,
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
        self.name        = name or "mcp"
        self.peer        = peer
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
            self.name    = found.name or self.name
            self._named  = True
            self._client = self._make_client()      # so the server sees the real name

    # === Being asked ================================================================

    async def answer(self, msg: ChatMessage) -> Reply:
        """A question asked of it; its text goes to the remote peer as it is."""
        return await self._ask_remote(msg.text)

    # === One question ===============================================================

    async def _ask_remote(self, text: str) -> Reply:
        """Asks the remote session, and turns whatever happens into one reply."""
        try:
            async with self._client as client:
                if client.protocol_version not in MODERN_PROTOCOL_VERSIONS:
                    raise RuntimeError("The server speaks only the handshake-era MCP protocol")
                peer = self.peer or await self._only_peer(client)
                if peer is None:
                    return Reply("%s: no single remote peer answers; name one with peer=" % self.name,
                                 status=ReplyStatus.ERROR)
                result = await client.call_tool("ask", {"peer": peer, "text": text},
                                                meta=self._lending(client), raise_on_error=False)
        except Exception as exc:
            logger.warning("%s could not ask its server: %r", self.name, exc)
            return Reply("%s: could not reach the remote session (%s)" % (self.name, type(exc).__name__),
                         status=ReplyStatus.ERROR)
        return _reply_from(result, self.name)

    async def _only_peer(self, client: Any) -> Optional[str]:
        """The only remote peer that answers, or None when there are none or several."""
        answering = [peer.name for peer in (await client.call_tool("peers")).data if peer.answers]
        return answering[0] if len(answering) == 1 else None

    # === Lending ====================================================================

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
