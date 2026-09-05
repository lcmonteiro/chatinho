"""The ``/help`` tool: lists what can be asked."""


from ..chat_hooks import (HookOnAsk, HookPeers, Peers,
                          declares, name_of, require, tool)
from ..chat_message import LOCAL, ChatMessage


@tool("help", "Lists the available tools")
@require(HookOnAsk)
@require(HookPeers)
class HelpCommand:
    """Answers with the tools registered in the chat it belongs to.

    A command is an ask addressed to a tool, so ``/help`` is this peer
    being asked. ``HookPeers`` is what lets it
    enumerate its siblings without ever seeing the session.
    """

    peers : Peers

    async def on_ask(self, msg: ChatMessage) -> str:
        """Returns one line per tool that can be asked.

        Args:
            msg: The question; its text is ignored.

        Returns:
            str: The listing, or a note when there is nothing to list.
        """
        lines = [
            "/%s - %s" % (name_of(who), getattr(who, "description", ""))
            for at, who in sorted(self.peers().items())
            if at != LOCAL and declares(who, HookOnAsk)
        ]
        return "Available tools:\n  " + "\n  ".join(lines) if lines else "No tools registered."
