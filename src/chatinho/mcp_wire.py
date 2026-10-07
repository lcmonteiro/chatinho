"""What crosses an MCP link: results, names and attachments.

Both ends share this module, so what :class:`~chatinho.frontends.mcp.McpFrontend`
writes is exactly what :class:`~chatinho.connectors.mcp.McpConnector` reads back.
It needs ``chatinho[mcp]``.
"""

import base64
import mimetypes
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

import mcp_types as types

from chatinho.chat_message import Attachment

#: Every result an ``ask`` can end in; exactly one per question.
STATUSES : Tuple[str, ...] = ("answered", "asked", "error", "timeout")

#: Where a client puts the credentials it lends, in a request's ``_meta``, and
#: the capability extension a server declares the ones it accepts under.
CREDENTIALS_KEY : str = "chatinho/credentials"

#: How long a question may take when nobody says otherwise, in seconds.
DEFAULT_DEADLINE : float = 120.0

_LINK = re.compile(r"\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")


@dataclass(frozen=True)
class RemoteAnswer:
    """One question's result, as the asking side reads it.

    Attributes:
        status: One of :data:`STATUSES`.
        text: The answer, the question back, or what went wrong.
        attachments: What the answer attached, bytes included.
        msg_id: The answer's message id in the remote session, when there is one.
    """

    status      : str
    text        : str
    attachments : Tuple[Attachment, ...] = ()
    msg_id      : Optional[str] = None


def result(
    status      : str,
    text        : str,
    attachments : Sequence[Attachment] = (),
    msg_id      : Optional[str] = None,
) -> types.CallToolResult:
    """Builds the tool result for one question.

    The structured content is what a chatinho client reads; the text block is
    for clients that only read text. ``error`` and ``timeout`` are tool errors.

    Args:
        status: One of :data:`STATUSES`.
        text: What to say.
        attachments: What the answer attached.
        msg_id: The answer's message id, for ``read_attachment``.

    Returns:
        types.CallToolResult: Ready to return from ``tools/call``.

    Raises:
        ValueError: *status* is not one of :data:`STATUSES`.
    """
    if status not in STATUSES:
        raise ValueError("A result's status is one of %s, got %r" % (", ".join(STATUSES), status))
    shown = text if status == "answered" else "[%s] %s" % (status, text)
    return types.CallToolResult(
        content=[types.TextContent(text=shown)],
        structured_content={
            "status"      : status,
            "text"        : text,
            "attachments" : [encode(item) for item in attachments],
            "msg_id"      : msg_id,
        },
        is_error=status in ("error", "timeout"),
    )


def read_result(res: types.CallToolResult) -> RemoteAnswer:
    """Reads back what :func:`result` wrote, or makes the best of a plain result.

    A server that is not a chatinho session answers with text alone: that is
    ``answered``, or ``error`` when the result is marked as one.
    """
    data = res.structured_content
    if isinstance(data, dict) and data.get("status") in STATUSES:
        return RemoteAnswer(
            status      = data["status"],
            text        = str(data.get("text", "")),
            attachments = tuple(decode(item) for item in data.get("attachments") or ()),
            msg_id      = data.get("msg_id"),
        )
    text = "\n".join(block.text for block in res.content if isinstance(block, types.TextContent))
    return RemoteAnswer("error" if res.is_error else "answered", text)


def safe_name(raw: Any, default: str) -> str:
    """A name that can stand in a peer path: non-empty, with no ``/``.

    Args:
        raw: What the other side called itself; anything.
        default: What to use when *raw* gives nothing usable.
    """
    if not isinstance(raw, str):
        return default
    name = " ".join(raw.replace("/", "-").split())
    return name or default


def linked_names(text: str) -> List[str]:
    """The relative link targets in a Markdown *text*, in order, each once.

    In chatinho a message links its attachments by name — ``[chart](chart.svg)``
    — and that is the only list of them there is. Absolute URLs, paths and
    anchors are not attachments.
    """
    names: List[str] = []
    for target in _LINK.findall(text or ""):
        if ":" in target or target.startswith(("/", "#")):
            continue
        name = unquote(target)
        if name not in names:
            names.append(name)
    return names


def read_link(url: Optional[str]) -> Optional[bytes]:
    """The bytes behind a ``file://`` link, or None for anything else or nothing there."""
    if not url:
        return None
    parsed = urlparse(url)
    if parsed.scheme != "file":
        return None
    try:
        with open(url2pathname(parsed.path), "rb") as handle:
            return handle.read()
    except OSError:
        return None


def media_type_of(name: str) -> str:
    """The media type a file called *name* most likely holds."""
    return mimetypes.guess_type(name)[0] or "application/octet-stream"


def encode(item: Attachment) -> Dict[str, str]:
    """An attachment as JSON: its name, media type and base64 content."""
    return {
        "name"       : item.name,
        "media_type" : item.media_type,
        "data_b64"   : base64.b64encode(item.data).decode("ascii"),
    }


def decode(data: Dict[str, Any]) -> Attachment:
    """Reads back what :func:`encode` wrote."""
    return Attachment(
        name       = str(data["name"]),
        media_type = str(data.get("media_type") or media_type_of(str(data["name"]))),
        data       = base64.b64decode(data.get("data_b64") or ""),
    )
