"""
Where ``HiveBackend`` keeps what waits to be sent, and, with a cache, a copy of the chat.

An :class:`Outbox` is the queue the sender takes from in order. Without a
cache it lives in memory; with one it is a table of :class:`HiveCache`, a
SQLite file that also keeps the chat's messages and attachments. Standard
library only; every call blocks, so ``HiveBackend`` makes them on a thread.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Protocol, Tuple

#: One item of the outbox: its kind (``message``, ``attachment`` or ``trace``) and its payload.
Item = Tuple[str, Dict[str, Any]]


class Outbox(Protocol):
    """What waits to reach the hive, oldest first."""

    def put(self, item: Item) -> int:
        """Adds *item* at the end; returns how many of the oldest were dropped to make room."""
        ...

    def peek(self, n: int) -> List[Item]:
        """The oldest *n* items, left in place."""
        ...

    def drop(self, n: int) -> None:
        """Removes the oldest *n* items, once the hive has them."""
        ...

    def __len__(self) -> int:
        ...


class MemoryOutbox:
    """An outbox in memory, bounded by *limit*."""

    def __init__(self, limit: int) -> None:
        raise NotImplementedError

    def put(self, item: Item) -> int:
        raise NotImplementedError

    def peek(self, n: int) -> List[Item]:
        raise NotImplementedError

    def drop(self, n: int) -> None:
        raise NotImplementedError

    def __len__(self) -> int:
        raise NotImplementedError


class HiveCache:
    """
    A local SQLite file holding a copy of the chat and the outbox, for the hive at *url*.

    Args:
        path: The file; made when missing.
        url: The hive the cache belongs to.
        limit: The most items its outbox holds.

    Raises:
        ValueError: If the file was made for another hive's URL.
    """

    def __init__(self, path: str, url: str, limit: int) -> None:
        raise NotImplementedError

    @property
    def outbox(self) -> Outbox:
        """The outbox kept in the file."""
        raise NotImplementedError

    def put_messages(self, messages: List[Dict[str, Any]]) -> None:
        """Keeps *messages*, as the wire writes them; one already kept is left as it is."""
        raise NotImplementedError

    def messages(self, since: Optional[datetime] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """The kept messages, oldest first, narrowed as ``load`` narrows."""
        raise NotImplementedError

    def forget(self, before: Optional[datetime] = None) -> int:
        """Drops the messages older than *before* and their attachments; returns how many went."""
        raise NotImplementedError

    def put_attachment(self, msg_id: str, name: str, media_type: str, data: bytes) -> None:
        """Keeps one attachment of *msg_id*."""
        raise NotImplementedError

    def attachment(self, msg_id: str, name: str) -> Optional[Tuple[str, bytes]]:
        """The media type and bytes of attachment *name* of *msg_id*, or None."""
        raise NotImplementedError

    def close(self) -> None:
        """Closes the file."""
        raise NotImplementedError
