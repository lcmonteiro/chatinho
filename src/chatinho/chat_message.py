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
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Sequence, Tuple
from urllib.parse import quote, unquote

#: The chat itself — the user's own id. Every connector is numbered from one.
LOCAL : int = 0

#: What a command speaks as. Commands are not peers and have no id of their
#: own, but what they write must not look like the user typing it: a connector
#: that answers what the user says would otherwise answer /help's output too.
TOOL : int = -1


@dataclass(frozen=True)
class Attachment:
    """Something a message carries that its text links to by name.

    A message is Markdown, and an attachment travels with it only when the
    text links to it — ``[chart](revenue.html)`` — so an attachment is never
    something a peer receives without being told what it is.

    Attributes:
        name: One relative path segment, e.g. ``revenue.html``; unique within
            its message, since it is what the text links to.
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
        attachments: What the text links to.
    """

    text        : str
    attachments : Tuple[Attachment, ...] = ()


@dataclass
class ChatMessage:
    """One message, addressed.

    Attributes:
        id: Unique within a chat, assigned by the store.
        text: What was said, as Markdown.
        frm: The id of whoever said it; :data:`LOCAL` for the user.
        to: The id it was addressed to, or None when it went to everyone.
        reply_to: The id of the message this answers, when it answers one.
        timestamp: When it entered the history.
        attachments: What the text links to; only linked ones are ever kept.
    """

    id          : str
    text        : str
    frm         : int = LOCAL
    to          : Optional[int] = None
    reply_to    : Optional[str] = None
    timestamp   : datetime = field(default_factory=datetime.now)
    attachments : Tuple[Attachment, ...] = ()

    @property
    def is_broadcast(self) -> bool:
        """Whether it went to everyone rather than to one peer."""
        return self.to is None

    @property
    def is_local(self) -> bool:
        """Whether the user said it."""
        return self.frm == LOCAL


# === Attachments ====================================================================

#: A fenced code block, ``` or ~~~, closed by the same fence or the end of the text.
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})[^\n]*\n.*?(?:^ {0,3}\1[ \t]*$|\Z)", re.M | re.S)

#: An inline code span: a run of backticks closed by a run of the same length.
_CODE_SPAN = re.compile(r"(`+)(?!`).+?(?<!`)\1(?!`)", re.S)

#: An inline link or image: ``[text](target)`` or ``![alt](target "title")``,
#: where the target may be wrapped in angle brackets.
_LINK = re.compile(
    r"!?\[(?:\\.|[^\\\]])*\]"
    r"\(\s*(?:<([^<>\n]*)>|([^\s()<>]+))(?:\s+(?:\"[^\"]*\"|'[^']*'))?\s*\)"
)

#: A URL scheme, as in ``https:`` or ``mailto:``.
_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


def _relative_targets(text: str) -> List[str]:
    """The relative link and image targets in *text*, as names, in order.

    Code is not Markdown that links anywhere, so fenced blocks and code spans
    are removed first: a sample showing ``[x](y.html)`` is not a link.

    Args:
        text: A message body.

    Returns:
        List[str]: Each relative target, ``./`` stripped and unquoted.
    """
    prose = _CODE_SPAN.sub("", _FENCE.sub("", text))
    targets : List[str] = []
    for match in _LINK.finditer(prose):
        target = link_target(match.group(1) if match.group(1) is not None else match.group(2))
        if target is not None:
            targets.append(target)
    return targets


def link_target(href: str) -> Optional[str]:
    """The attachment name a link points at, or None when it is an ordinary link.

    Absolute links (a scheme, ``/`` or ``//``), fragments (``#``) and anything
    with a query are ordinary links. The rest name an attachment of the same
    message: ``./`` is stripped and percent-escapes are decoded.

    Args:
        href: A link target, as written in the text.

    Returns:
        Optional[str]: The attachment name, or None.
    """
    href = href.strip()
    if not href or _SCHEME.match(href) or href.startswith(("/", "#")) or "?" in href:
        return None
    if href.startswith("./"):
        href = href[2:]
    return unquote(href) or None


def _check_name(name: str) -> None:
    """Raises ValueError unless *name* is one relative path segment."""
    if not name or name in (".", "..") or "/" in name or "\\" in name:
        raise ValueError("Attachment name %r must be one relative path segment" % name)


def attached(text: str, attachments: Sequence[Attachment]) -> Tuple[Attachment, ...]:
    """The attachments that travel with *text*: the ones it links to.

    Args:
        text: The message body, as Markdown.
        attachments: What the speaker attached.

    Returns:
        Tuple[Attachment, ...]: The linked attachments, in the order given;
        unlinked ones are dropped.

    Raises:
        ValueError: If a name is not one relative path segment, two share a
            name, or the text links to a relative name nothing carries.
    """
    names : Dict[str, Attachment] = {}
    for item in attachments:
        _check_name(item.name)
        if item.name in names:
            raise ValueError("Two attachments are named %r" % item.name)
        names[item.name] = item
    linked = _relative_targets(text)
    missing = [target for target in linked if target not in names]
    if missing:
        raise ValueError("The text links to %s, which is not attached" % ", ".join(
            repr(target) for target in dict.fromkeys(missing)))
    wanted = set(linked)
    return tuple(item for item in attachments if item.name in wanted)


def attachment_url(base: Optional[str], msg: ChatMessage, href: str) -> Optional[str]:
    """Where an attachment link in *msg* points: ``<base>/m/<id>/<name>``.

    Args:
        base: The attachment server's address, or None when there is none.
        msg: The message the link is in.
        href: The link's target, as written.

    Returns:
        Optional[str]: The URL, or None without a base or when *href* is not
        a relative link to one of *msg*'s attachments.
    """
    name = link_target(href)
    if base is None or name is None or name not in {item.name for item in msg.attachments}:
        return None
    return "%s/m/%s/%s" % (base.rstrip("/"), quote(msg.id, safe=""), quote(name, safe=""))


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
