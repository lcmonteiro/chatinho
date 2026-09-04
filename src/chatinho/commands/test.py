"""The ``/test`` tool: checks the chat is wired up, writing as it goes."""

from typing import Any, Optional

from ..chat_hooks import (HookOnAsk, HookParticipants, HookSay, Participants, Say,
                          name_of, require, tool)
from ..chat_message import LOCAL, ChatMessage


@tool("test", "Checks the chat is wired up")
@require(HookOnAsk)
@require(HookSay)
@require(HookParticipants)
class TestCommand:
    """Reports each check as it happens instead of one block at the end.

    ``HookSay`` is what makes that possible: the chat hands over ``say``, so
    the tool can write while it works and still answer at the end.
    """

    say          : Say
    participants : Participants

    def __init__(self, session: Optional[Any] = None) -> None:
        # Optional: only a backend round-trip needs it, and most chats have none.
        self.session = session

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
        await self.say("Backend: %s" % self._check_backend())
        return "Checks done."

    def _check_backend(self) -> str:
        """Round-trips a value through the backend, when there is one."""
        session = self.session
        if session is None or getattr(session, "backend", None) is None:
            return "none configured"
        key, data = "__chatinho_test__", {"ok": True}
        try:
            session.save_data(key, data)
            loaded = session.load_data(key)
            session.delete_data(key)
        except RuntimeError as exc:
            return "incomplete (%s)" % exc
        return "ok" if loaded == data else "save/load mismatch"
