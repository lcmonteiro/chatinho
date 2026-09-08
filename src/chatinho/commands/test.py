"""The ``/test`` command: checks the chat is wired up, writing as it goes."""

from typing import Optional

from ..chat_hooks import Context, HookContext, HookExecute, HookPeers, HookSay, Peers, Say, require, tool
from ..chat_message import LOCAL


@tool("test", "Checks the chat is wired up")
@require(HookExecute)
@require(HookSay)
@require(HookContext)
@require(HookPeers)
class TestCommand:
    """Reports each check as it happens instead of one block at the end.

    ``HookSay`` is what makes that possible: a command writes into the
    conversation only if it declared it. What it reports on is what it was
    granted; nothing else is reachable.
    """

    say     : Say
    context : Context
    peers   : Peers

    async def execute(self, args: str = "", by: int = LOCAL, **kwargs) -> Optional[str]:
        """Runs the checks, saying each one, and answers with the verdict.

        Args:
            args: Ignored.
            by: The id of the peer that ran it.
            **kwargs: Ignored.

        Returns:
            Optional[str]: A one-line verdict.
        """
        del args, kwargs
        await self.say("Running checks…")
        connected = sorted(getattr(w, "name", "?") for at, w in self.peers().items() if at != LOCAL)
        await self.say("Peers: %s" % (", ".join(connected) or "none"))
        await self.say("Context: %d message(s) in reach" % len(self.context()))
        return "Checks done, for peer %d." % by
