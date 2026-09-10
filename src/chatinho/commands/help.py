"""The ``/help`` command: lists what can be run."""

from ..chat_hooks import HookExecute, HookPeers, HookCommands, HookSay, Commands, Peers, Say, require, tool
from ..chat_message import LOCAL


@tool("help", "Lists the available commands")
@require(HookExecute)
@require(HookPeers)
@require(HookCommands)
@require(HookSay)
class HelpCommand:
    """Answers with the commands registered in the chat it belongs to.

    A command is not a peer: nothing is addressed to it and it hears nothing.
    It runs, and it answers whoever ran it. ``HookPeers`` is only so the
    listing can mention who else is connected.
    """

    peers    : Peers
    commands : Commands
    say      : Say

    async def execute(self, args: str = "", by: int = LOCAL, **kwargs) -> str:
        """Answers with the listing.

        It does not say it: what a command answers is posted by the session, in
        ``TOOL``'s name, replying to the invocation. Saying it too would put it
        in the conversation twice.

        Args:
            args: Ignored.
            by: The id of the peer that ran it.
            **kwargs: Ignored.

        Returns:
            str: The listing.
        """
        del args, by, kwargs
        lines = ["/%s - %s" % (name, getattr(cmd, "description", ""))
                 for name, cmd in sorted(self.commands().items())]
        listing = "Commands:\n  " + "\n  ".join(lines) if lines else "No commands registered."

        others = sorted(getattr(w, "name", "?") for at, w in self.peers().items() if at != LOCAL)
        return listing + ("\n\nConnected: %s" % ", ".join(others) if others else "")
