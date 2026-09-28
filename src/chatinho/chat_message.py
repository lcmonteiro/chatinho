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

import re
import secrets
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

#: The chat itself — the user's own id. Every connector is numbered from one.
LOCAL : int = 0

#: What a command speaks as. Commands are not peers and have no id of their
#: own, but what they write must not look like the user typing it: a connector
#: that answers what the user says would otherwise answer /help's output too.
TOOL : int = -1


@dataclass(frozen=True)
class Attachment:
    """Something a peer attaches to what it says: a page, an image, a file.

    It never rides on the message. The session hands it to the backend that
    declared ``HookKeep``, under the message's id, and the message's Markdown
    text links to it by name — ``[chart](revenue.html)``. Opening one is asking
    ``locate`` where it is.

    Attributes:
        name: What the text links to, e.g. ``revenue.html``.
        media_type: What the content is, e.g. ``text/html``.
        data: The content itself.
    """

    name       : str
    media_type : str
    data       : bytes


@dataclass(frozen=True)
class Reply:
    """What ``answer`` or a command's ``execute`` returns when it attaches.

    Returning a plain string still works; a Reply is only for an answer that
    carries attachments.

    Attributes:
        text: The answer, as Markdown.
        attachments: What the reply attaches; they go to the backend.
    """

    text        : str
    attachments : Tuple[Attachment, ...] = ()


@dataclass
class ChatMessage:
    """One message, addressed.

    Attributes:
        id: Unique across every chat that shares an archive: ``msg-`` and 16
            random hex characters, assigned by the store. The terminal shows
            its :func:`short_id`.
        text: What was said, as Markdown.
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


#: A full id as :meth:`MessageStore.new_id` makes it.
_FULL_ID = re.compile(r"msg-([0-9a-f]{16})")


def short_id(msg_id: str) -> str:
    """The id to show a person: the first 7 hex characters, as git shortens hashes.

    Only for display — everything the library stores, returns or accepts is the
    full id. An id not in the ``msg-`` + 16-hex form (one given explicitly, or
    from an archive older than this form) is shown as it is.

    Args:
        msg_id: A message id.

    Returns:
        str: ``3f9a1c2`` for ``msg-3f9a1c2e7b04d5a6``; *msg_id* otherwise.
    """
    match = _FULL_ID.fullmatch(msg_id)
    return match.group(1)[:7] if match else msg_id


class MessageStore:
    """The chat's message history: ids, lookup and reply threading.

    The full history is kept here; how much of it a widget paints is the
    widget's business.
    """

    def __init__(self) -> None:
        self._messages     : List[ChatMessage] = []
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
        """Returns a fresh message id: ``msg-`` and 16 random hex characters.

        Random, not counted, so a chat that reopens on an archive never hands
        out an id already in it — a counter would start at one again. 64 bits
        make a collision negligible, and there is no state to guard, so it is
        safe to call from any thread.
        """
        return "msg-" + secrets.token_hex(8)

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
