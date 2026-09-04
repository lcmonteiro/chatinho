"""The ``/test`` tool: checks the chat is wired up, writing as it goes."""

from ..chat_hooks import (Context, HookContext, HookOnAsk, HookParticipants, HookSay,
                          Participants, Say, name_of, require, tool)
from ..chat_message import LOCAL, ChatMessage


@tool("test", "Checks the chat is wired up")
@require(HookOnAsk)
@require(HookSay)
@require(HookParticipants)
@require(HookContext)
class TestCommand:
    """Reports each check as it happens instead of one block at the end.

    ``HookSay`` is what makes that possible: the chat hands over ``say``, so
    the tool can write while it works and still answer at the end. What it
    reports on is what it was granted — nothing else is reachable.
    """

    say          : Say
    participants : Participants
    context      : Context

    async def on_ask(self, msg: ChatMessage) -> str:
        """Runs the checks and returns the verdict.

        Args:
            msg: The question; its text is ignored.

        Returns:
            str: A one-line verdict, after the details have been said.
        """
        await self.say("Running checks…")
        others = [name_of(w) for at, w in self.participants().items() if at != LOCAL]
        await self.say("Participants: %s" % (", ".join(sorted(others)) or "none"))
        await self.say("Context: %d message(s) in reach" % len(self.context()))
        return "Checks done."
