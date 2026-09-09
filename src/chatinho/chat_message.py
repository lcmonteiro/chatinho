"""Message model and history for chatinho.

Every peer in a chat has an integer id, and :data:`LOCAL` — zero — is
the chat itself: the user. A connector links the chat to one agent or
subsystem and carries both an ``id``, which is how messages are addressed, and
a ``name``, which is what the chat displays. Keeping them apart is what lets a
connector be renamed without breaking the replies already in flight.

A message says where it came from and where it is going, and that is all the
routing there is:

    to is None   → everyone heard it          (say)
    to is an id  → one peer was asked  (ask)
    reply_to set → it answers that message    (answer)

Neither class touches Textual, so both can be exercised without mounting an
application.
"""

import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

#: The chat itself — the user's own id. Every connector is numbered from one.
LOCAL : int = 0

#: What a command speaks as. Commands are not peers and have no id of their
#: own, but what they write must not look like the user typing it: a connector
#: that answers what the user says would otherwise answer /help's output too.
TOOL : int = -1


@dataclass
class ChatMessage:
    """One message, addressed.

    Attributes:
        id: Unique within a chat, assigned by the store.
        text: What was said.
        frm: The id of whoever said it; :data:`LOCAL` for the user.
        to: The id it was addressed to, or None when it went to everyone.
        reply_to: The id of the message this answers, when it answers one.
        timestamp: When it entered the history.
    """

    id        : str
    text      : str
    frm       : int = LOCAL
    to        : Optional[int] = None
    reply_to  : Optional[str] = None
    timestamp : datetime = field(default_factory=datetime.now)

    @property
    def is_broadcast(self) -> bool:
        """Whether it went to everyone rather than to one peer."""
        return self.to is None

    @property
    def is_local(self) -> bool:
        """Whether the user said it."""
        return self.frm == LOCAL


class MessageStore:
    """The chat's message history: ids, lookup and reply threading.

    The full history is kept here; how much of it a widget paints is the
    widget's business.
    """

    def __init__(self) -> None:
        self._messages     : List[ChatMessage] = []
        self._next_id      : int = 1
        self._id_lock      : threading.Lock = threading.Lock()
        self._index        : Dict[str, ChatMessage] = {}
        self._replies      : Dict[str, List[str]] = {}

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
            msg_id = "msg-%d" % self._next_id
            self._next_id += 1
        return msg_id

    def add(self, msg: ChatMessage) -> ChatMessage:
        """Appends *msg*, indexes it and records it against what it answers.

        Args:
            msg: The message to keep.

        Returns:
            ChatMessage: The same message, for chaining.
        """
        self._messages.append(msg)
        self._index[msg.id] = msg
        if msg.reply_to is not None:
            self._replies.setdefault(msg.reply_to, []).append(msg.id)
        return msg

    def find(self, msg_id: str) -> Optional[ChatMessage]:
        """Returns the message with *msg_id*, or None."""
        return self._index.get(msg_id)

    def replies(self, msg_id: str) -> List[str]:
        """Returns the ids of the messages that answer *msg_id*."""
        return list(self._replies.get(msg_id, []))
