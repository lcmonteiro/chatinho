"""What part of the conversation a peer asks for.

A :class:`Query` is plain data — no callables — so the session can apply it to
what it holds today, and a backend could translate the same value into its own
query tomorrow. Every field narrows; they combine with AND.
"""

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Iterable, List, Optional, Set

from .message import ChatMessage, MessageID, ReplyStatus

#: Whoever asks: ``context()`` resolves it to the asking peer's id. Beside
#: ``LOCAL`` (0) and ``TOOL`` (-1), and like them never a real peer's id.
SELF : int = -2


@dataclass(frozen=True)
class Query:
    """Which messages of the conversation to return.

    Attributes:
        peer: Messages from this peer, to it, or replying to one of its
            messages. :data:`SELF` means the peer asking.
        thread: The reply chain of this message: it, every message it replies
            to up to the root, and every reply to a message in that chain.
        errors: When False, replies whose status is ``error`` are left out.
        since: Messages stamped at or after this moment.
        limit: At most this many, the newest.
    """

    peer   : Optional[int] = None
    thread : Optional[MessageID] = None
    errors : bool = True
    since  : Optional[datetime] = None
    limit  : Optional[int] = None

    def last(self, n: int) -> "Query":
        """The same query, keeping at most the *n* newest."""
        return replace(self, limit=n)

    def select(self, messages: Iterable[ChatMessage], asker: Optional[int] = None) -> List[ChatMessage]:
        """Applies the query to *messages*, oldest first, as asked by *asker*."""
        msgs = list(messages)
        if not self.errors:
            msgs = [m for m in msgs if m.status != ReplyStatus.ERROR]
        if self.since is not None:
            msgs = [m for m in msgs if m.timestamp >= self.since]
        if self.peer is not None:
            peer  = asker if self.peer == SELF else self.peer
            from_ = {m.id for m in msgs if m.frm == peer}
            msgs  = [m for m in msgs if m.frm == peer or m.to == peer or m.reply_to in from_]
        if self.thread is not None:
            chain = _chain(msgs, self.thread)
            msgs  = [m for m in msgs if m.id in chain or m.reply_to in chain]
        if self.limit is not None:
            msgs = msgs[-self.limit:] if self.limit > 0 else []
        return msgs


def _chain(msgs: List[ChatMessage], start: MessageID) -> Set[MessageID]:
    """The ids from *start* up its ``reply_to`` links to the root."""
    by_id = {m.id: m for m in msgs}
    chain : Set[MessageID] = set()
    at : Optional[MessageID] = start
    while at is not None and at not in chain:
        chain.add(at)
        found = by_id.get(at)
        at = found.reply_to if found is not None else None
    return chain
