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

_PREFIX : str = "msg-"
_FULL   : int = 16
_HEX    = re.compile(r"[0-9a-f]+")


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


#: What an answer can say about itself. ``answered`` is the default and covers
#: "I don't know" too, said in the text; ``asked`` is a question back to the
#: asker; ``error`` is a peer that could not answer.
ANSWER_STATUSES : Tuple[str, ...] = ("answered", "asked", "error")


@dataclass(frozen=True)
class Reply:
    """What ``answer`` or a command's ``execute`` returns when it says more than text.

    Returning a plain string still works; a Reply is for an answer that carries
    attachments, or that is not a plain answer.

    Attributes:
        text: The answer, as Markdown.
        attachments: What the reply attaches; they go to the backend.
        status: One of :data:`ANSWER_STATUSES`; ``answered`` when left out.
    """

    text        : str
    attachments : Tuple[Attachment, ...] = ()
    status      : str = "answered"

    def __post_init__(self) -> None:
        if self.status not in ANSWER_STATUSES:
            raise ValueError("A reply's status is one of %s, got %r"
                             % (", ".join(ANSWER_STATUSES), self.status))


class Secret:
    """A value that must never be shown: a credential lent for one question.

    ``repr`` and ``str`` are redacted, so a Secret in a log line, an error or a
    traceback's locals says nothing. :meth:`reveal` is the one way to the value.
    """

    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        self._value = value

    def reveal(self) -> str:
        """Returns the value itself."""
        return self._value

    def __repr__(self) -> str:
        return "Secret('***')"

    __str__ = __repr__


@dataclass(frozen=True)
class MessageID:
    """A message's id: random, unique across sessions, and not a string.

    ``str()`` gives the form that is stored and logged — ``msg-`` and 16 hex
    characters — and :meth:`parse` reads it back. :attr:`short` is what a person
    sees, the first 7 hex characters, as git shortens a commit hash.

    Attributes:
        hex: The hex digits after ``msg-``: 16 for a new id, any number for one
            read from an archive older than this form.
    """

    hex : str

    def __post_init__(self) -> None:
        if not isinstance(self.hex, str) or not _HEX.fullmatch(self.hex):
            raise ValueError("A message id is lowercase hex digits, got %r" % (self.hex,))

    @classmethod
    def new(cls) -> "MessageID":
        """Returns a fresh id: 16 random hex characters.

        Random, not counted, so a chat that reopens on an archive never hands
        out an id already in it — a counter would start at one again. 64 bits
        make a collision negligible, and there is no state to guard, so it is
        safe to call from any thread.
        """
        return cls(secrets.token_hex(8))

    @classmethod
    def parse(cls, text: str) -> "MessageID":
        """Reads back what ``str()`` wrote.

        Args:
            text: ``msg-`` and hex digits, e.g. ``msg-3f9a1c2e7b04d5a6``.

        Returns:
            MessageID: The id *text* names.

        Raises:
            ValueError: If *text* is not ``msg-`` and hex digits.
        """
        if not isinstance(text, str) or not text.startswith(_PREFIX):
            raise ValueError("A message id starts with %r, got %r" % (_PREFIX, text))
        return cls(text[len(_PREFIX):])

    @property
    def short(self) -> str:
        """What to show a person: ``3f9a1c2`` for ``msg-3f9a1c2e7b04d5a6``.

        Only for display. An id not 16 hex characters long — from an older
        archive — is shown whole, as ``str()`` writes it.
        """
        return self.hex[:7] if len(self.hex) == _FULL else str(self)

    def __str__(self) -> str:
        return _PREFIX + self.hex


@dataclass
class ChatMessage:
    """One message, addressed.

    Attributes:
        id: Unique across every chat that shares an archive, assigned by the
            store. The terminal shows its :attr:`MessageID.short`.
        text: What was said, as Markdown.
        frm: The id of whoever said it; :data:`LOCAL` for the user.
        to: The id it was addressed to, or None when it went to everyone.
        reply_to: The id of the message this answers, when it answers one.
        timestamp: When it entered the history.
        status: What an answer said about itself — one of
            :data:`ANSWER_STATUSES`, from the ``Reply`` that made it;
            ``answered`` for everything else. Not kept by the archive.
    """

    id        : MessageID
    text      : str
    frm       : int = LOCAL
    to        : Optional[int] = None
    reply_to  : Optional[MessageID] = None
    timestamp : datetime = field(default_factory=datetime.now)
    status    : str = "answered"

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
        self._index        : Dict[MessageID, ChatMessage] = {}
        self._replies      : Dict[MessageID, List[MessageID]] = {}

    @property
    def messages(self) -> List[ChatMessage]:
        """The full history, oldest first.

        A copy: the list is the store's own state, and handing callers a
        reference to it lets them append or clear the history by accident.
        The messages themselves are shared — only the list is copied.
        """
        return list(self._messages)

    def new_id(self) -> MessageID:
        """Returns a fresh message id; see :meth:`MessageID.new`."""
        return MessageID.new()

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

    def find(self, msg_id: MessageID) -> Optional[ChatMessage]:
        """Returns the message with *msg_id*, or None."""
        return self._index.get(msg_id)

    def replies(self, msg_id: MessageID) -> List[MessageID]:
        """Returns the ids of the messages that answer *msg_id*."""
        return list(self._replies.get(msg_id, []))
