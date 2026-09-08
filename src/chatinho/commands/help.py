"""The ``/help`` command: lists what can be run."""

from typing import Any, Optional

from ..chat_hooks import HookExecute, HookPeers, HookSay, Peers, Say, require, tool
from ..chat_message import LOCAL


@tool("help", "Lists the available commands")
@require(HookExecute)
@require(HookPeers)
@require(HookSay)
class HelpCommand:
    """Answers with the commands registered in the chat it belongs to.

    A command is not a peer: nothing is addressed to it and it hears nothing.
    It runs, and it answers whoever ran it. ``HookPeers`` is only so the
    listing can mention who else is connected.
    """

    peers : Peers
    say   : Say

    def __init__(self, commands: Optional[Any] = None) -> None:
        #: Set by the session at registration, so /help can list its siblings.
        self.commands = commands

    async def execute(self, args: str = "", by: int = LOCAL, **kwargs) -> str:
        """Writes the listing into the conversation, and answers with it too.

        Args:
            args: Ignored.
            by: The id of the peer that ran it.
            **kwargs: Ignored.

        Returns:
            str: The listing.
        """
        del args, by, kwargs
        lines = ["/%s - %s" % (name, getattr(cmd, "description", ""))
                 for name, cmd in sorted((self.commands or {}).items())]
        listing = "Commands:\n  " + "\n  ".join(lines) if lines else "No commands registered."

        others = sorted(getattr(w, "name", "?") for at, w in self.peers().items() if at != LOCAL)
        answer = listing + ("\n\nConnected: %s" % ", ".join(others) if others else "")
        await self.say(answer)
        return answer
