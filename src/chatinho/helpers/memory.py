"""What ``OpenAIConnector`` and ``AgentConnector`` agree on: what a model remembers, and who said it.

Standard library only, so either connector can import it without the other's
library.
"""

from typing import Any, Dict, List, Optional, Tuple

from chatinho.hooks import Context, name_of
from chatinho.message import LOCAL, ChatMessage
from chatinho.query import SELF, Query

#: What a model remembers by default: what passed between it and anyone,
#: without the replies that failed, the last twenty.
MEMORY = Query(peer=SELF, errors=False).last(20)


def earlier(context: Context, memory: Optional[Query], question: ChatMessage) -> List[ChatMessage]:
    """What *memory* selects from the conversation, without *question* itself.

    The question is in the conversation too, so one more is asked for and the
    question left out: it must not eat into the limit.

    Args:
        context: The ``context`` grant of the peer remembering.
        memory: Which messages to remember; None for none.
        question: The message being answered.

    Returns:
        List[ChatMessage]: Oldest first, at most ``memory.limit`` of them.
    """
    if memory is None:
        return []
    limit = memory.limit
    query = memory if limit is None else memory.last(limit + 1)
    found = [m for m in context(query) if m.id != question.id]
    if limit is not None:
        found = found[-limit:] if limit > 0 else []
    return found


def speaker(m: ChatMessage, me: Optional[int], roster: Dict[int, Any]) -> Tuple[str, str]:
    """The role *m* plays for the model remembering it, and its text as the model reads it.

    The model's own words are the ``assistant``'s; the user's are the ``user``'s
    as they were said; anyone else's are the ``user``'s too, prefixed with the
    speaker's name, or its number when it is no longer in the room.

    Args:
        m: A remembered message.
        me: The remembering peer's id.
        roster: The peers in the room, by id.

    Returns:
        Tuple[str, str]: ``("assistant" | "user", text)``.
    """
    if m.frm == me:
        return "assistant", m.text
    if m.frm == LOCAL:
        return "user", m.text
    who = name_of(roster[m.frm]) if m.frm in roster else str(m.frm)
    return "user", "%s: %s" % (who, m.text)
