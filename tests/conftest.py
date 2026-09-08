"""A headless peer, shared by the tests that drive a session directly.

The conversation is protected: nothing calls ``session._say``. A peer
declares the hooks it needs and the session hands the capabilities over at
``attach``. :class:`Driver` is the presentation with the terminal taken out —
the same declarations ``_Chat`` makes — so a test drives a chat exactly the way
the TUI does.
"""

from typing import Any, List, Optional

import pytest

from chatinho import (
    LOCAL,
    Answer,
    Ask,
    ChatMessage,
    HookAsk,
    HookContext,
    HookOnAsk,
    HookOnSay,
    HookPeers,
    HookInvoke,
    HookSay,
    Context,
    Peers,
    Invoke,
    Say,
    connector,
    require,
)
from chatinho.chat_session import ChatSession


@connector("driver")
@require(HookSay)
@require(HookAsk)
@require(HookOnSay)
@require(HookOnAsk)
@require(HookContext)
@require(HookPeers)
@require(HookInvoke)
class Driver:
    """Everything the presentation is, minus the terminal."""

    # Granted by the session at attach.
    say           : Say
    ask           : Ask
    answer        : Answer
    context : Context
    peers         : Peers
    invoke        : Invoke

    def __init__(self, answers: Optional[List[str]] = None) -> None:
        self.heard   : List[ChatMessage] = []
        self.asked   : List[ChatMessage] = []
        #: Queued replies for questions put to the user; None means "say nothing".
        self.answers : List[str] = list(answers or [])

    async def on_say(self, msg: ChatMessage) -> None:
        """Records every broadcast that reached us."""
        self.heard.append(msg)

    async def on_ask(self, msg: ChatMessage) -> Optional[str]:
        """Records the question and answers it from the queue, if it has one."""
        self.asked.append(msg)
        return self.answers.pop(0) if self.answers else None

    def texts(self) -> List[str]:
        """The whole history as plain strings, oldest first."""
        return [m.text for m in self.context()]

    def id_of(self, name: str) -> Optional[int]:
        """The id of the peer with that visible name."""
        return next((i for i, w in self.peers().items()
                     if getattr(w, "name", "") == name), None)

    async def command(self, name: str, args: str = "") -> Any:
        """Runs ``/name args``. A command is not a peer: it is run, not asked."""
        return await self.invoke(name, args)


async def driven(**kwargs) -> tuple:
    """Builds a started session with a :class:`Driver` at :data:`LOCAL`.

    Args:
        **kwargs: Passed straight to :class:`~chatinho.chat_session.ChatSession`.

    Returns:
        tuple: The session and its driver.
    """
    session = ChatSession(**kwargs)
    view    = Driver()
    session.attach(view, at=LOCAL)
    await session.start()
    return session, view


@pytest.fixture
async def chat():
    """A started session with a driver attached, for the common case."""
    session, view = await driven()
    yield session, view
    await session.close()
