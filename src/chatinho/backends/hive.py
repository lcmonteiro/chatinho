"""
A backend that keeps the chat in a hive: the server every chat is kept and seen in.

It speaks HTTP with the standard library, off the loop, so a chat needs no
extra to be kept in a hive. Everything it is given goes to an outbox first and
a sender task takes it to the hive in order, so a hive that is slow or down
never holds up the chat. With ``cache=`` the outbox and a copy of the chat live
in a local SQLite file, so the chat keeps its history offline and nothing
queued is lost across a restart.
"""

import asyncio
import base64
import json
import logging
import re
import shutil
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..hooks import HookForget, HookKeep, HookLink, HookListen, HookLoad, HookPeers, HookRecord, Peers
from ..hooks import backend, name_of, require
from ..message import TOOL, Attachment, ChatMessage, ChatTrace, MessageID
from ..support.parts.hive import KEY_HEADER, message_from_wire, message_to_wire, trace_to_wire
from ..support.parts.keys import KeyUnavailable, read_async
from ..support.parts.keys.sources import KeyLike, to_source
from .hive_cache import HiveCache, Item, MemoryOutbox, Outbox

logger = logging.getLogger(__name__)

#: How many messages or traces one request carries at most.
BATCH : int = 100

#: The first wait after a failed send, and the longest; it doubles in between.
FIRST_WAIT : float = 0.5
LONGEST_WAIT : float = 30.0


class HiveUnavailable(ConnectionError):
    """The hive could not be reached for something that cannot wait: ``forget``."""


class _Unreachable(Exception):
    """No answer, or a server error: worth trying again."""


class _Refused(Exception):
    """The hive does not take the key: trying again changes nothing."""


class _Rejected(Exception):
    """The hive refused what was sent as malformed: trying again changes nothing."""


# @req REQ-BACK-009, REQ-BACK-010, REQ-BACK-011, REQ-BACK-012, REQ-BACK-013
@backend("hive")
@require(HookListen)
@require(HookLoad)
@require(HookForget)
@require(HookKeep)
@require(HookLink)
@require(HookRecord)
@require(HookPeers)
class HiveBackend:
    """
    Keeps the chat's conversation, attachments and traces in a hive.

    Args:
        url: The hive's address, ``http://`` or ``https://``.
        key: The chat's key, or a key source read when each request is made.
        cache: A local SQLite file to keep a copy of the chat and the outbox
            in; None keeps the outbox in memory only.
        timeout: The most seconds one request may take.
        queue_limit: The most items the outbox holds; past it the oldest go.
        flush_timeout: The most seconds ``shutdown`` spends sending what is left.

    Raises:
        ValueError: If *url* is not ``http`` or ``https``, or a limit is not positive.
    """

    peers : Peers

    # @req REQ-BACK-011
    def __init__(
        self,
        url           : str,
        key           : KeyLike,
        *,
        cache         : Optional[str] = None,
        timeout       : float = 10.0,
        queue_limit   : int = 10000,
        flush_timeout : float = 3.0,
    ) -> None:
        parsed = urllib.parse.urlparse(url) if isinstance(url, str) else None
        if parsed is None or parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError("A hive's URL is http:// or https://, got %r" % (url,))
        if isinstance(queue_limit, bool) or not isinstance(queue_limit, int) or queue_limit < 1:
            raise ValueError("queue_limit must be a positive integer, got %r" % (queue_limit,))
        for name, value in (("timeout", timeout), ("flush_timeout", flush_timeout)):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
                raise ValueError("%s must be a number of seconds, got %r" % (name, value))
        source = to_source(key)
        if source is None:
            raise ValueError("A hive needs the chat's key")
        self.url           = url.rstrip("/")
        self.cache         = cache
        self.timeout       = float(timeout)
        self.queue_limit   = queue_limit
        self.flush_timeout = float(flush_timeout)
        self._key          = source
        self._store        : Optional[HiveCache] = None
        self._outbox       : Outbox = MemoryOutbox(queue_limit)
        self._putting      = asyncio.Lock()
        self._wake         = asyncio.Event()
        self._sender       : Optional["asyncio.Task[None]"] = None
        self._closing      = False
        self._lost         = 0
        # Said once per outage, and once per refusal, rather than on every retry.
        self._said_down    = False
        self._said_refused = False
        self._files        : Optional[Path] = None

    def __repr__(self) -> str:
        return "HiveBackend(url=%r, cache=%r)" % (self.url, self.cache)

    # === Lifecycle ==================================================================

    # @req REQ-BACK-011, REQ-BACK-013
    async def initialize(self) -> None:
        """Opens the cache, if any, and starts the task that sends the outbox."""
        if self.cache is not None and self._store is None:
            self._store  = await asyncio.to_thread(HiveCache, self.cache, self.url, self.queue_limit)
            self._outbox = self._store.outbox
        if self._sender is None:
            self._wake   = asyncio.Event()
            self._sender = asyncio.create_task(self._send_forever(), name="hive-sender")
            if await self._waiting():
                self._wake.set()

    # @req REQ-BACK-010, REQ-BACK-011, REQ-BACK-013
    async def shutdown(self) -> None:
        """Sends what is left for at most ``flush_timeout`` seconds, then says what was lost or kept."""
        self._closing = True
        self._wake.set()
        loop     = asyncio.get_running_loop()
        deadline = loop.time() + self.flush_timeout
        while self._sender is not None and not self._sender.done() and await self._waiting() \
                and loop.time() < deadline:
            await asyncio.sleep(0.05)
        if self._sender is not None:
            self._sender.cancel()
            try:
                await self._sender
            except (asyncio.CancelledError, Exception):
                pass
            self._sender = None
        left = await self._waiting()
        if self._store is not None:
            if left:
                logger.warning("%d items for the hive at %s are kept in the cache %s for the next run",
                               left, self.url, self.cache)
            await asyncio.to_thread(self._store.close)
            self._store = None
        else:
            self._lost += left
        if self._lost:
            logger.warning("%d items for the hive at %s were lost", self._lost, self.url)
        if self._files is not None:
            shutil.rmtree(self._files, ignore_errors=True)
            self._files = None

    # === What the chat hands over ===================================================

    # @req REQ-BACK-009, REQ-BACK-011, REQ-BACK-013
    async def listen(self, msg: ChatMessage) -> None:
        """Puts *msg* in the outbox; returns without waiting on the network."""
        wire = message_to_wire(msg, self._name(msg.frm))
        await self._put(("message", wire))
        if self._store is not None:
            await asyncio.to_thread(self._store.put_messages, [wire])

    # @req REQ-BACK-010, REQ-BACK-013
    async def keep(self, msg_id: MessageID, attachments: Sequence[Attachment]) -> None:
        """Puts *attachments* in the outbox, under *msg_id*."""
        for item in attachments:
            await self._put(("attachment", {"msg_id": str(msg_id), "name": item.name,
                                            "media_type": item.media_type,
                                            "data": base64.b64encode(item.data).decode("ascii")}))
            if self._store is not None:
                await asyncio.to_thread(self._store.put_attachment, str(msg_id), item.name, item.media_type,
                                        item.data)

    # @req REQ-BACK-009
    async def record(self, trace: ChatTrace) -> None:
        """Puts *trace* in the outbox."""
        await self._put(("trace", trace_to_wire(trace, self._name(trace.frm))))

    # === What the chat asks for =====================================================

    # @req REQ-BACK-009, REQ-BACK-011, REQ-BACK-012, REQ-BACK-013
    async def load(self, since: Optional[datetime] = None, limit: Optional[int] = None) -> List[ChatMessage]:
        """The chat's messages from the hive, or from the cache when the hive cannot answer."""
        params : Dict[str, str] = {}
        if since is not None:
            params["since"] = since.isoformat()
        if limit is not None:
            params["limit"] = str(limit)
        try:
            _, body, _ = await self._request("GET", "/api/messages", params=params)
            wires = json.loads(body)["messages"]
            if self._store is not None:
                await asyncio.to_thread(self._store.put_messages, wires)
            return [message_from_wire(w) for w in wires]
        except _Refused as exc:
            logger.error("The hive at %s refused the chat's key (%s)", self.url, exc)
        except (_Unreachable, _Rejected) as exc:
            logger.warning("The hive at %s cannot be reached (%s)", self.url, exc)
        except (ValueError, KeyError) as exc:
            logger.warning("The hive at %s answered what is not a conversation (%s)", self.url, exc)
        if self._store is None:
            return []
        wires = await asyncio.to_thread(self._store.messages, since, limit)
        logger.warning("Loaded %d messages from the cache %s instead", len(wires), self.cache)
        return [message_from_wire(w) for w in wires]

    # @req REQ-BACK-009, REQ-BACK-011, REQ-BACK-013
    async def forget(self, before: Optional[datetime] = None) -> int:
        """
        Forgets the chat's messages older than *before*, in the hive and the cache.

        Raises:
            HiveUnavailable: If the hive cannot be reached, or refuses the key.
        """
        params = {} if before is None else {"before": before.isoformat()}
        try:
            _, body, _ = await self._request("DELETE", "/api/messages", params=params)
        except (_Unreachable, _Refused, _Rejected) as exc:
            raise HiveUnavailable("The hive at %s could not forget: %s" % (self.url, exc)) from None
        if self._store is not None:
            await asyncio.to_thread(self._store.forget, before)
        return int(json.loads(body)["forgotten"])

    # @req REQ-BACK-010, REQ-BACK-011, REQ-BACK-013
    async def link(self, msg_id: MessageID, name: str) -> Optional[str]:
        """A local file holding attachment *name* of *msg_id*, or None when there is none."""
        data : Optional[bytes] = None
        path = "/api/messages/%s/attachments/%s" % (urllib.parse.quote(str(msg_id), safe=""),
                                                     urllib.parse.quote(name, safe=""))
        try:
            status, body, _ = await self._request("GET", path, missing_ok=True)
            data = None if status == 404 else body
        except (_Unreachable, _Refused, _Rejected) as exc:
            logger.warning("The hive at %s cannot give %s of %s (%s)", self.url, name, msg_id, exc)
        if data is None and self._store is not None:
            found = await asyncio.to_thread(self._store.attachment, str(msg_id), name)
            data  = None if found is None else found[1]
        if data is None:
            return None
        if self._files is None:
            self._files = Path(tempfile.mkdtemp(prefix="chatinho-hive-"))
        folder = self._files / msg_id.hex
        folder.mkdir(exist_ok=True)
        target = folder / (re.sub(r"[^\w.\-]", "_", Path(name).name) or "attachment")
        await asyncio.to_thread(target.write_bytes, data)
        return str(target)

    # === The sender =================================================================

    async def _put(self, item: Item) -> None:
        """Adds *item* to the outbox, in the order the calls came, and wakes the sender."""
        async with self._putting:
            if self._store is not None:
                dropped = await asyncio.to_thread(self._outbox.put, item)
            else:
                dropped = self._outbox.put(item)
        if dropped:
            logger.warning("The outbox for the hive at %s is full: %d items dropped, the oldest first",
                           self.url, dropped)
        self._wake.set()

    async def _waiting(self) -> int:
        if self._store is not None:
            return await asyncio.to_thread(len, self._outbox)
        return len(self._outbox)

    async def _peek(self) -> List[Item]:
        if self._store is not None:
            return await asyncio.to_thread(self._outbox.peek, BATCH)
        return self._outbox.peek(BATCH)

    async def _drop(self, n: int) -> None:
        async with self._putting:
            if self._store is not None:
                await asyncio.to_thread(self._outbox.drop, n)
            else:
                self._outbox.drop(n)

    # @req REQ-BACK-011, REQ-BACK-012
    async def _send_forever(self) -> None:
        """Takes the outbox to the hive, in order, until cancelled."""
        wait = FIRST_WAIT
        while True:
            items = await self._peek()
            if not items:
                self._wake.clear()
                if await self._waiting():
                    continue
                await self._wake.wait()
                continue
            kind = items[0][0]
            run  = [items[0]] if kind == "attachment" else [i for i in _leading(items, kind)]
            try:
                await self._send(kind, [payload for _, payload in run])
            except _Refused as exc:
                if not self._said_refused:
                    logger.error("The hive at %s refused the chat's key (%s); what it refuses is dropped",
                                 self.url, exc)
                    self._said_refused = True
                self._lost += len(run)
            except _Rejected as exc:
                logger.error("The hive at %s refused %d %s as malformed (%s); dropped",
                             self.url, len(run), kind, exc)
                self._lost += len(run)
            except _Unreachable as exc:
                if not self._said_down:
                    logger.warning("The hive at %s cannot be reached (%s); %d items wait", self.url, exc,
                                   await self._waiting())
                    self._said_down = True
                try:
                    await asyncio.wait_for(self._woken_to_close(), 0.2 if self._closing else wait)
                except asyncio.TimeoutError:
                    pass
                wait = min(wait * 2, LONGEST_WAIT)
                continue
            else:
                if self._said_down:
                    logger.info("The hive at %s is back", self.url)
                self._said_down    = False
                self._said_refused = False
            wait = FIRST_WAIT
            await self._drop(len(run))

    async def _woken_to_close(self) -> None:
        """Returns once the backend is closing: a wait between retries ends early then."""
        while not self._closing:
            self._wake.clear()
            await self._wake.wait()

    async def _send(self, kind: str, payloads: List[Dict[str, Any]]) -> None:
        if kind == "message":
            await self._request("POST", "/api/messages", body={"messages": payloads})
        elif kind == "trace":
            await self._request("POST", "/api/traces", body={"traces": payloads})
        else:
            [one] = payloads
            path  = "/api/messages/%s/attachments/%s" % (urllib.parse.quote(one["msg_id"], safe=""),
                                                         urllib.parse.quote(one["name"], safe=""))
            await self._request("PUT", path, raw=base64.b64decode(one["data"]), media_type=one["media_type"])

    # === HTTP =======================================================================

    async def _request(
        self,
        method     : str,
        path       : str,
        *,
        params     : Optional[Dict[str, str]] = None,
        body       : Optional[Dict[str, Any]] = None,
        raw        : Optional[bytes] = None,
        media_type : str = "application/json",
        missing_ok : bool = False,
    ) -> Tuple[int, bytes, Dict[str, str]]:
        """Makes one request off the loop; raises what kind of failure it was."""
        try:
            key = (await read_async(self._key)).reveal()
        except KeyUnavailable as exc:
            raise _Unreachable("the chat's key is unavailable: %s" % exc) from None
        url = self.url + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        data = raw if raw is not None else (json.dumps(body).encode("utf-8") if body is not None else None)
        request = urllib.request.Request(url, data=data, method=method,
                                         headers={KEY_HEADER: key, "Content-Type": media_type,
                                                  "Accept": "application/json"})
        return await asyncio.to_thread(self._open, request, missing_ok)

    def _open(self, request: urllib.request.Request, missing_ok: bool) -> Tuple[int, bytes, Dict[str, str]]:
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as answer:
                return answer.status, answer.read(), dict(answer.headers)
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                raise _Refused("HTTP %d" % exc.code) from None
            if exc.code == 404 and missing_ok:
                return 404, b"", {}
            if exc.code >= 500 or exc.code in (408, 429):
                raise _Unreachable("HTTP %d" % exc.code) from None
            raise _Rejected("HTTP %d" % exc.code) from None
        except (urllib.error.URLError, OSError) as exc:
            raise _Unreachable(type(getattr(exc, "reason", exc)).__name__) from None

    def _name(self, frm: int) -> str:
        """What the hive shows for *frm*: its name in the chat, ``tool`` for a command."""
        if frm == TOOL:
            return "tool"
        try:
            roster = self.peers()
        except AttributeError:                                  # not attached to a session yet
            return str(frm)
        return name_of(roster[frm]) if frm in roster else str(frm)


def _leading(items: List[Item], kind: str) -> List[Item]:
    """The items at the front of *items* that are all of *kind*."""
    run = []
    for item in items:
        if item[0] != kind:
            break
        run.append(item)
    return run
