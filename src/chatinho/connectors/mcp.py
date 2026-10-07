"""A peer that puts questions to another chatinho session over MCP.

:class:`McpConnector` is an ordinary connector: it appears in the chat under a
name it chooses (``@lab``), and a message addressed to it — ``@lab will it
rain?`` — is said in the remote session through its one ``say`` tool, and the
first reply to it comes back.
Exactly one reply comes back for every such message.

It speaks the modern MCP protocol (2026-07-28). When a remote peer needs an LLM,
the connector can lend it a credential for that one question — out of band,
only one the server declared, and only over HTTPS or to this machine. Without
``delegate``, no key ever leaves this machine.
"""

import asyncio
import base64
import ipaddress
import logging
import mimetypes
from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping, Optional, Tuple, Union
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
from chatinho.chat_message import TOOL, Attachment, ChatMessage, Reply

logger = logging.getLogger(__name__)

#: Every result a say can end in; exactly one per message.
STATUSES : Tuple[str, ...] = ("answered", "asked", "error", "timeout")

#: Where a client puts the credentials it lends, in a request's ``_meta``, and
#: the capability extension a server declares the ones it accepts under.
CREDENTIALS_KEY : str = "chatinho/credentials"

#: How long a message may wait for its reply when nobody says otherwise, in seconds.
DEFAULT_DEADLINE : float = 120.0


# === What comes back from the server ==============================================

@dataclass(frozen=True)
class _Remote:
    """One question's result, as the asking side reads it.

    Attributes:
        status: One of :data:`STATUSES`.
        text: The answer, the question back, or what went wrong.
        attachments: What the answer attached, bytes included.
        msg_id: The answer's message id in the remote session, when there is one.
    """

    status      : str
    text        : str
    attachments : Tuple[Attachment, ...] = ()
    msg_id      : Optional[str] = None


def _read_result(res: types.CallToolResult) -> _Remote:
    """Reads back what ``McpFrontend`` wrote, or makes the best of a plain result.

    A server that is not a chatinho session answers with text alone: that is
    ``answered``, or ``error`` when the result is marked as one.
    """
    data = res.structured_content
    if isinstance(data, dict) and data.get("status") in STATUSES:
        return _Remote(
            status      = data["status"],
            text        = str(data.get("text", "")),
            attachments = tuple(_decode(item) for item in data.get("attachments") or ()),
            msg_id      = data.get("msg_id"),
        )
    text = "\n".join(block.text for block in res.content if isinstance(block, types.TextContent))
    return _Remote("error" if res.is_error else "answered", text)


def _decode(data: Dict[str, Any]) -> Attachment:
    """Reads back an attachment as ``McpFrontend`` encoded it."""
    return Attachment(
        name       = str(data["name"]),
        media_type = str(data.get("media_type") or _media_type_of(str(data["name"]))),
        data       = base64.b64decode(data.get("data_b64") or ""),
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


def _media_type_of(name: str) -> str:
    """The media type a file called *name* most likely holds."""
    return mimetypes.guess_type(name)[0] or "application/octet-stream"

#: How much longer than its deadline a question may take before the link is
#: taken to be hung. The server answers within the deadline; this only guards
#: against a server that never does.
_GRACE : float = 30.0


@connector("mcp")
@require(HookListen)
@require(HookAnswer)
@require(HookSay)
@require(HookPeers)
class McpConnector:
    """Puts questions to a remote chatinho session.

    Give it exactly one server: an HTTP ``url`` with its bearer ``token``, or
    a ``server`` object (an in-process ``mcp`` ``Server``, or an
    ``McpFrontend``'s ``.server``).

    Args:
        url: The Streamable HTTP endpoint, e.g. ``https://lab.example/mcp``.
        token: The bearer token the server requires; needed with *url*.
        server: An in-process server, for tests and embedding.
        name: Its name in the chat, and the client name the server sees; the
            server's name when left out.
        deadline: How long the remote session may take for each question, in
            seconds; the server's own default when left out.
        delegate: Credentials to lend, by name: a value, or a function returning
            one for each question. Only the ones the server declares are sent,
            and only over HTTPS or to this machine.

    Raises:
        ValueError: Not exactly one server, a *url* without a *token*, or a
            non-positive deadline.
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
        deadline    : Optional[float] = None,
        delegate    : Optional[Mapping[str, Union[str, Callable[[], str]]]] = None,
    ) -> None:
        if (url is None) == (server is None):
            raise ValueError("Give exactly one of url or server")
        if url is not None and not token:
            raise ValueError("An HTTP server needs its bearer token")
        if deadline is not None and deadline <= 0:
            raise ValueError("deadline must be positive")
        self._url        = url
        self._token      = token
        self._server     = server
        self._named      = name is not None
        self.name        = _safe_name(name, "mcp") if name is not None else "mcp"
        self.deadline    = deadline
        self._delegate   = dict(delegate or {})
        self._client     : Any = None
        self._runner     : Optional["asyncio.Task[None]"] = None
        self._stop       : Optional[asyncio.Event] = None

    # === Lifecycle ==================================================================

    async def initialize(self) -> None:
        """Connects, and takes the server's name when none was given.

        A server that cannot be reached is not fatal: the chat goes on, and the
        next question tries again and answers that it could not.
        """
        try:
            client = await self._connect()
        except Exception as exc:
            logger.warning("%s could not reach its server: %s", self.name, exc)
            return
        if not self._named and client.server_info is not None:
            self.name   = _safe_name(client.server_info.name, self.name)
            self._named = True
            # The server saw the placeholder name; the next requests carry the real one.
            self._disconnect()

    def shutdown(self) -> None:
        """Closes the link."""
        self._disconnect()

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
            return Reply("%s: lending credentials needs HTTPS; nothing was sent" % self.name, status="error")
        args : Dict[str, Any] = {"text": text, "asker": asker}
        if self.deadline is not None:
            args["deadline_ms"] = int(self.deadline * 1000)
        limit = (self.deadline or DEFAULT_DEADLINE * 5) + _GRACE
        try:
            client = await self._connect()
            meta   = self._lending(client)
            got    = await asyncio.wait_for(client.call_tool("say", args, meta=meta), limit)
        except asyncio.TimeoutError:
            return Reply("%s: timeout — the remote session never answered" % self.name, status="error")
        except Exception as exc:
            logger.warning("%s could not ask its server: %r", self.name, exc)
            self._disconnect()
            return Reply("%s: could not reach the remote session (%s)" % (self.name, type(exc).__name__),
                         status="error")
        return self._reply_for(_read_result(got))

    def _reply_for(self, got: _Remote) -> Reply:
        if got.status == "answered":
            return Reply(got.text, tuple(got.attachments))
        if got.status == "asked":
            return Reply("%s asks: %s" % (self.name, got.text), status="asked")
        return Reply("%s: %s — %s" % (self.name, got.status, got.text), status="error")

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
        found    = client.session.discover_result
        declared = ((found.capabilities.extensions or {}).get(CREDENTIALS_KEY) or {}) if found else {}
        lent     = {name: (value() if callable(value) else value)
                    for name, value in self._delegate.items() if name in declared}
        return {CREDENTIALS_KEY: lent} if lent else None

    # === The link ===================================================================

    async def _connect(self) -> Any:
        """The open client, opening it first when there is none."""
        if self._client is not None and self._runner is not None and not self._runner.done():
            return self._client
        loop  = asyncio.get_running_loop()
        ready : "asyncio.Future[Any]" = loop.create_future()
        self._stop   = asyncio.Event()
        self._runner = asyncio.create_task(self._run(ready, self._stop))
        return await ready

    async def _run(self, ready: "asyncio.Future[Any]", stop: asyncio.Event) -> None:
        """Holds the client open in a task of its own, which is where it must close."""
        try:
            async with AsyncExitStack() as stack:
                client = await stack.enter_async_context(self._make_client(stack))
                if client.session.protocol_version not in MODERN_PROTOCOL_VERSIONS:
                    raise RuntimeError("The server speaks only the handshake-era MCP protocol")
                self._client = client
                ready.set_result(client)
                await stop.wait()
        except Exception as exc:
            if not ready.done():
                ready.set_exception(exc)
            else:
                logger.warning("%s lost its server: %r", self.name, exc)
        finally:
            self._client = None

    def _disconnect(self) -> None:
        if self._stop is not None:
            self._stop.set()
        self._client = None

    def _make_client(self, stack: AsyncExitStack) -> Any:
        from mcp import Client
        options : Dict[str, Any] = dict(
            mode        = "auto",
            client_info = types.Implementation(name=self.name, version="chatinho"),
        )
        if self._server is not None:
            return Client(self._server, **options)
        import httpx2
        from mcp.client.streamable_http import streamable_http_client
        http = httpx2.AsyncClient(
            headers={"Authorization": "Bearer %s" % self._token},
            timeout=httpx2.Timeout(30.0, read=300.0),
        )
        stack.push_async_callback(http.aclose)
        return Client(streamable_http_client(str(self._url), http_client=http), **options)
