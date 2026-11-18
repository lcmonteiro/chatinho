"""
What a chat and the hive exchange: the JSON of a message and of a trace, and the key header.

``HiveBackend`` writes it and the hive reads it, and the other way round; both
import this part so neither imports the other. Standard library only.

A message travels as::

    {"id": "msg-…", "text": "…", "frm": 0, "frm_name": "me", "to": null,
     "reply_to": null, "timestamp": "2026-11-18T21:15:00", "status": "answered"}

and a trace as::

    {"id": "trc-…", "msg_id": "msg-…", "state": "running", "text": "extract",
     "frm": 1, "frm_name": "dev", "prev": null, "timestamp": "2026-11-18T21:15:01"}

``frm_name`` is what the speaker was called when it was sent: an id is
numbered per session, and the hive shows who spoke long after.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from ...message import ChatMessage, ChatTrace, MessageID, ReplyStatus, TraceID, TraceState

#: The header every request to the hive carries its key in.
KEY_HEADER : str = "X-Hive-Key"


# @req REQ-BACK-009, REQ-HIVE-004
def message_to_wire(msg: ChatMessage, frm_name: str) -> Dict[str, Any]:
    """
    *msg* as JSON-ready data, with the speaker's name beside its id.

    Credentials never go: they are lent for answering, not kept.
    """
    return {
        "id"        : str(msg.id),
        "text"      : msg.text,
        "frm"       : msg.frm,
        "frm_name"  : frm_name,
        "to"        : msg.to,
        "reply_to"  : None if msg.reply_to is None else str(msg.reply_to),
        "timestamp" : msg.timestamp.isoformat(),
        "status"    : ReplyStatus(msg.status).value,
    }


# @req REQ-BACK-009, REQ-HIVE-004
def message_from_wire(data: Dict[str, Any]) -> ChatMessage:
    """
    The message *data* holds.

    Raises:
        ValueError: If *data* is not a message as :func:`message_to_wire` writes one.
    """
    if not isinstance(data, dict):
        raise ValueError("A message is an object, got %r" % (type(data).__name__,))
    try:
        return ChatMessage(
            id        = MessageID.parse(_text(data, "id")),
            text      = _text(data, "text"),
            frm       = _int(data, "frm"),
            to        = _optional_int(data, "to"),
            reply_to  = MessageID.parse(_optional_text(data, "reply_to")),
            timestamp = _time(data, "timestamp"),
            status    = ReplyStatus(data.get("status", ReplyStatus.ANSWERED.value)),
        )
    except (KeyError, TypeError) as exc:
        raise ValueError("Not a message: %s" % exc) from None


# @req REQ-HIVE-005
def trace_to_wire(trace: ChatTrace, frm_name: str) -> Dict[str, Any]:
    """*trace* as JSON-ready data, with the tracer's name beside its id."""
    return {
        "id"        : str(trace.id),
        "msg_id"    : str(trace.msg_id),
        "state"     : TraceState(trace.state).value,
        "text"      : trace.text,
        "frm"       : trace.frm,
        "frm_name"  : frm_name,
        "prev"      : None if trace.prev is None else str(trace.prev),
        "timestamp" : trace.timestamp.isoformat(),
    }


# @req REQ-HIVE-005
def trace_from_wire(data: Dict[str, Any]) -> ChatTrace:
    """
    The trace *data* holds.

    Raises:
        ValueError: If *data* is not a trace as :func:`trace_to_wire` writes one.
    """
    if not isinstance(data, dict):
        raise ValueError("A trace is an object, got %r" % (type(data).__name__,))
    prev = _optional_text(data, "prev")
    try:
        return ChatTrace(
            id        = TraceID.parse(_text(data, "id")),
            msg_id    = MessageID.parse(_text(data, "msg_id")),
            state     = TraceState(_text(data, "state")),
            text      = _text(data, "text"),
            frm       = _int(data, "frm"),
            prev      = None if prev is None else TraceID.parse(prev),
            timestamp = _time(data, "timestamp"),
        )
    except (KeyError, TypeError) as exc:
        raise ValueError("Not a trace: %s" % exc) from None


def _text(data: Dict[str, Any], name: str) -> str:
    value = data.get(name)
    if not isinstance(value, str):
        raise ValueError("%r must be a string, got %r" % (name, value))
    return value


def _optional_text(data: Dict[str, Any], name: str) -> Optional[str]:
    return None if data.get(name) is None else _text(data, name)


def _int(data: Dict[str, Any], name: str) -> int:
    value = data.get(name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("%r must be an integer, got %r" % (name, value))
    return value


def _optional_int(data: Dict[str, Any], name: str) -> Optional[int]:
    return None if data.get(name) is None else _int(data, name)


def _time(data: Dict[str, Any], name: str) -> datetime:
    return datetime.fromisoformat(_text(data, name))
