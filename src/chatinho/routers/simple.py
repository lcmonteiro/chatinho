"""The builders' router: a reply goes back to its author, and anything else to the lone peer that answers."""

from typing import Optional

from ..hooks import HookAnswer, HookContext, HookPeers, HookRoute, Context, Peers, declares, require
from ..message import LOCAL, ChatMessage


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

    async def route(self, msg: ChatMessage) -> Optional[int]:
        """
        The peer that answers *msg*, or None.

        Args:
            msg: A say with ``to`` unset.

        Returns:
            Optional[int]: The id of the author of what it replies to, or of
            the lone peer that answers; None when there is no such peer.
        """
        roster = self.peers()

        def answers(at: Optional[int]) -> bool:
            return (at is not None and at not in (msg.frm, LOCAL)
                    and at in roster and declares(roster[at], HookAnswer))

        if msg.reply_to is not None:
            parent = next((m for m in self.context() if m.id == msg.reply_to), None)
            author = parent.frm if parent is not None else None
            return author if answers(author) else None
        answering = [at for at in roster if answers(at)]
        return answering[0] if len(answering) == 1 else None
