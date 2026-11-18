"""
A backend that keeps the chat in a hive: the server every chat is kept and seen in.

It speaks HTTP with the standard library, off the loop, so a chat needs no
extra to be kept in a hive. Everything it is given goes to an outbox first and
a sender task takes it to the hive in order, so a hive that is slow or down
never holds up the chat. With ``cache=`` the outbox and a copy of the chat live
in a local SQLite file, so the chat keeps its history offline and nothing
queued is lost across a restart.
"""

import logging
from datetime import datetime
from typing import List, Optional, Sequence

from ..hooks import HookForget, HookKeep, HookLink, HookListen, HookLoad, HookPeers, HookRecord, Peers
from ..hooks import backend, require
from ..message import Attachment, ChatMessage, ChatTrace, MessageID
from ..support.parts.keys.sources import KeyLike

logger = logging.getLogger(__name__)


class HiveUnavailable(ConnectionError):
    """The hive could not be reached for something that cannot wait: ``forget``."""


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
        raise NotImplementedError

    async def initialize(self) -> None:
        """Opens the cache, if any, and starts the task that sends the outbox."""
        raise NotImplementedError

    async def shutdown(self) -> None:
        """Sends what is left for at most ``flush_timeout`` seconds, then says what was lost or kept."""
        raise NotImplementedError

    async def listen(self, msg: ChatMessage) -> None:
        """Puts *msg* in the outbox; returns without waiting on the network."""
        raise NotImplementedError

    async def load(self, since: Optional[datetime] = None, limit: Optional[int] = None) -> List[ChatMessage]:
        """The chat's messages from the hive, or from the cache when the hive cannot answer."""
        raise NotImplementedError

    async def forget(self, before: Optional[datetime] = None) -> int:
        """
        Forgets the chat's messages older than *before*, in the hive and the cache.

        Raises:
            HiveUnavailable: If the hive cannot be reached.
        """
        raise NotImplementedError

    async def keep(self, msg_id: MessageID, attachments: Sequence[Attachment]) -> None:
        """Puts *attachments* in the outbox, under *msg_id*."""
        raise NotImplementedError

    async def link(self, msg_id: MessageID, name: str) -> Optional[str]:
        """A local file holding attachment *name* of *msg_id*, or None when there is none."""
        raise NotImplementedError

    async def record(self, trace: ChatTrace) -> None:
        """Puts *trace* in the outbox."""
        raise NotImplementedError
