"""The builders' router: a reply goes back to its author, and anything else to the lone peer that answers."""

from typing import Any, Dict, List, Optional

from ..hooks import HookAnswer, HookContext, HookPeers, HookRoute, Context, Peers, declares, require
from ..message import LOCAL, ChatMessage


# @req REQ-ROUTE-007
def answering(msg: ChatMessage, roster: Dict[int, Any]) -> List[int]:
    """
    The peers that could answer *msg*: those that answer, but its speaker and the frontend.

    Args:
        msg: A say with ``to`` unset.
        roster: The peers in the room, by id.

    Returns:
        List[int]: Their ids, in roster order.
    """
    return [at for at, who in roster.items()
            if at not in (msg.frm, LOCAL) and declares(who, HookAnswer)]


# @req REQ-ROUTE-004, REQ-ROUTE-005, REQ-ROUTE-007
def simple_route(msg: ChatMessage, roster: Dict[int, Any], context: Context) -> Optional[int]:
    """
    ``SimpleRouter``'s two rules, for any router that wants them first.

    A say that replies to a message goes to that message's author, and any
    other say to the one peer that answers; each only when that is another
    peer that answers, and neither counts the frontend.

    Args:
        msg: A say with ``to`` unset.
        roster: The peers in the room, by id.
        context: The ``context`` grant, to find what *msg* replies to.

    Returns:
        Optional[int]: The peer the rules choose, or None.
    """
    candidates = answering(msg, roster)
    if msg.reply_to is not None:
        parent = next((m for m in context() if m.id == msg.reply_to), None)
        author = parent.frm if parent is not None else None
        return author if author in candidates else None
    return candidates[0] if len(candidates) == 1 else None


# @req REQ-ROUTE-004, REQ-ROUTE-005
@require(HookRoute)
@require(HookPeers)
@require(HookContext)
class SimpleRouter:
    """
    Routes by two rules, and reads the room through the same grants any router would.

    A say that replies to a message goes to that message's author; any other
    say goes to the one peer that answers. Neither counts the speaker or the
    frontend, which speaks for the person, and either answers None when it
    finds nobody, or more than one. It holds nothing, so one instance serves
    a session for its whole life.
    """

    name     : str = "router"
    peers    : Peers
    context  : Context

    # @req REQ-ROUTE-004, REQ-ROUTE-005
    async def route(self, msg: ChatMessage) -> Optional[int]:
        """
        The peer that answers *msg*, or None.

        Args:
            msg: A say with ``to`` unset.

        Returns:
            Optional[int]: The id of the author of what it replies to, or of
            the lone peer that answers; None when there is no such peer.
        """
        return simple_route(msg, self.peers(), self.context)
