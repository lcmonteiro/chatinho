"""Message model and history for chatinho.

Neither class touches Textual, so both can be exercised without mounting an
application.
"""

import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class ChatMessage:
    """Represents a chat message."""

    id          : str
    text        : str
    timestamp   : datetime = field(default_factory=datetime.now)
    is_command  : bool = False
    reply_to    : Optional[str] = None
    is_sent_by_me : bool = True
    # Set when the message came in through a connector rather than from the
    # chat itself; ``correlation_id`` is the far side's own id for the
    # exchange, and is what routes the user's reply back.
    origin         : Optional[str] = None
    correlation_id : Optional[str] = None


class MessageStore:
    """The chat's message history: ids, lookup and reply threading.

    The full history is kept here; the rendering window (see :meth:`window`)
    only decides how much of it a widget paints.
    """

    def __init__(self) -> None:
        self._messages     : List[ChatMessage] = []
        self._next_id      : int = 1
        self._id_lock      : threading.Lock = threading.Lock()
        self._index        : Dict[str, ChatMessage] = {}
        # Mapping from message id to list of reply ids (for threading)
        self._replies      : Dict[str, List[str]] = {}
        self._replies_lock : threading.Lock = threading.Lock()

    @property
    def messages(self) -> List[ChatMessage]:
        """The full history, oldest first.

        A copy: the list is the store's own state, and handing callers a
        reference to it lets them append or clear the history by accident.
        The messages themselves are shared — only the list is copied.
        """
        return list(self._messages)

    def new_id(self) -> str:
        """Returns a fresh message id. Safe to call from any thread."""
        with self._id_lock:
            msg_id = f"msg-{self._next_id}"
            self._next_id += 1
        return msg_id

    def add(self, msg: ChatMessage) -> ChatMessage:
        """Appends *msg* to the history, threading it if it is a reply.

        Args:
            msg: The message to store.

        Returns:
            ChatMessage: The stored message, for chaining.
        """
        self._messages.append(msg)
        self._index[msg.id] = msg
        if msg.reply_to is not None:
            self.record_reply(msg.reply_to, msg.id)
        return msg

    def record_reply(self, reply_to: str, msg_id: str) -> None:
        """Thread-safely records that *msg_id* replies to *reply_to*."""
        with self._replies_lock:
            self._replies.setdefault(reply_to, []).append(msg_id)

    def replies(self, msg_id: str) -> List[str]:
        """Returns the ids of the messages that reply to *msg_id*."""
        with self._replies_lock:
            return list(self._replies.get(msg_id, []))

    def find(self, msg_id: str) -> Optional[ChatMessage]:
        """Returns the message with the given id, or None."""
        return self._index.get(msg_id)

    def window(self, size: int) -> List[ChatMessage]:
        """Returns the last *size* messages, oldest first.

        Args:
            size: How many messages the window holds.

        Returns:
            List[ChatMessage]: The tail of the history, at most *size* long.
        """
        start = max(0, len(self._messages) - size)
        return self._messages[start:]
