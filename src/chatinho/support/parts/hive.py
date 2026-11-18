"""
What a chat and the hive exchange: the JSON of a message and of a trace, and the key header.

``HiveBackend`` writes it and the hive reads it, and the other way round; both
import this part so neither imports the other. Standard library only.
"""

from typing import Any, Dict

from ...message import ChatMessage, ChatTrace

#: The header every request to the hive carries its key in.
KEY_HEADER : str = "X-Hive-Key"


def message_to_wire(msg: ChatMessage, frm_name: str) -> Dict[str, Any]:
    """
    *msg* as JSON-ready data, with the speaker's name beside its id.

    Credentials never go: they are lent for answering, not kept.
    """
    raise NotImplementedError


def message_from_wire(data: Dict[str, Any]) -> ChatMessage:
    """
    The message *data* holds.

    Raises:
        ValueError: If *data* is not a message as :func:`message_to_wire` writes one.
    """
    raise NotImplementedError


def trace_to_wire(trace: ChatTrace, frm_name: str) -> Dict[str, Any]:
    """*trace* as JSON-ready data, with the tracer's name beside its id."""
    raise NotImplementedError


def trace_from_wire(data: Dict[str, Any]) -> ChatTrace:
    """
    The trace *data* holds.

    Raises:
        ValueError: If *data* is not a trace as :func:`trace_to_wire` writes one.
    """
    raise NotImplementedError
