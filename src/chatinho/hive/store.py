"""
Everything the hive keeps, in one SQL database: chats, admin keys, messages, attachments, traces.

Plain synchronous SQLAlchemy; the app calls it from a thread pool. Messages
and traces are kept as the wire writes them, per chat, and a resend of one
already kept is skipped.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


class NameTaken(ValueError):
    """A chat by that name already exists."""


@dataclass(frozen=True)
class Caller:
    """
    Who a key belongs to.

    Attributes:
        admin: Whether it is an admin key.
        chat: The chat's name, for a chat key; None for an admin.
    """

    admin : bool
    chat  : Optional[str] = None


class Store:
    """
    The hive's database.

    Args:
        db_url: Any URL SQLAlchemy accepts; the tables are made when missing.
    """

    def __init__(self, db_url: str) -> None:
        raise NotImplementedError

    def close(self) -> None:
        """Closes the connections."""
        raise NotImplementedError

    # === Chats and keys =============================================================

    def add_chat(self, name: str, key_hash: str) -> None:
        """
        Makes chat *name*, known by *key_hash*.

        Raises:
            ValueError: If *name* is not 1 to 64 of ``a-z 0-9 - _``.
            NameTaken: If a chat already has *name*.
        """
        raise NotImplementedError

    def remove_chat(self, name: str) -> bool:
        """Deletes chat *name* and everything kept for it; False when there was none."""
        raise NotImplementedError

    def chats(self) -> List[Dict[str, Any]]:
        """Every chat: ``name``, ``created``, ``messages`` (how many) and ``last`` (last write, or None)."""
        raise NotImplementedError

    def add_admin(self, key_hash: str) -> None:
        """Makes an admin known by *key_hash*."""
        raise NotImplementedError

    def who(self, key_hash: str) -> Optional[Caller]:
        """Who *key_hash* belongs to, or None."""
        raise NotImplementedError

    # === A chat's records ===========================================================

    def put_messages(self, chat: str, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Keeps *messages* in *chat*; returns those that were new."""
        raise NotImplementedError

    def messages(
        self, chat: str, since: Optional[datetime] = None, limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """*chat*'s messages, oldest first: those after *since*, the last *limit* of them."""
        raise NotImplementedError

    def forget(self, chat: str, before: Optional[datetime] = None) -> int:
        """Drops *chat*'s messages older than *before*, with their attachments and traces."""
        raise NotImplementedError

    def put_attachment(self, chat: str, msg_id: str, name: str, media_type: str, data: bytes) -> None:
        """Keeps one attachment; a second with the same name replaces the first."""
        raise NotImplementedError

    def attachment(self, chat: str, msg_id: str, name: str) -> Optional[Tuple[str, bytes]]:
        """The media type and bytes of one attachment, or None."""
        raise NotImplementedError

    def put_traces(self, chat: str, traces: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Keeps *traces* in *chat*; returns those that were new."""
        raise NotImplementedError

    def traces(self, chat: str, msg_id: str) -> List[Dict[str, Any]]:
        """The traces of *msg_id* in *chat*, oldest first."""
        raise NotImplementedError

    def has_chat(self, name: str) -> bool:
        """Whether chat *name* exists."""
        raise NotImplementedError
