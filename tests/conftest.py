"""A headless presentation, shared by the tests that drive a session directly.

The conversation is protected: nothing calls ``session._send_message``. A
plugin declares the hooks it needs and the session hands the capabilities over
at ``attach``. :class:`Driver` is that plugin with the terminal taken out — the
same declarations ``_Chat`` makes — so a test drives a chat exactly the
way the TUI does.
"""

from typing import Callable, List

import pytest

from chatinho import (
    ChatMessage,
    HookLoadMessages,
    HookReceiveCommand,
    HookReceiveMessage,
    HookSay,
    HookSendCommand,
    HookSendMessage,
    require,
)
from chatinho.chat_session import ChatSession


@require(HookSendMessage)
@require(HookSendCommand)
@require(HookLoadMessages)
@require(HookSay)
@require(HookReceiveMessage)
@require(HookReceiveCommand)
class Driver:
    """Everything a presentation is, minus the terminal."""

    # Granted by the session at attach.
    send_message  : Callable[..., str]
    send_command  : Callable[[str], str]
    load_messages : Callable[..., List[ChatMessage]]
    say           : Callable[..., str]

    def __init__(self) -> None:
        self.received  : List[ChatMessage] = []
        self.commanded : List[ChatMessage] = []
        self.sent      : List[ChatMessage] = []

    def on_receive_message(self, msg: ChatMessage, **kwargs) -> None:
        """Records every message, split by who sent it."""
        self.received.append(msg)
        if msg.is_sent_by_me:
            self.sent.append(msg)

    def on_receive_command(self, msg: ChatMessage, **kwargs) -> None:
        """Records every command, before the session dispatches it."""
        self.commanded.append(msg)
        self.sent.append(msg)


def driven(**kwargs) -> tuple:
    """Builds a session with a :class:`Driver` attached.

    Args:
        **kwargs: Passed straight to :class:`~chatinho.chat_session.ChatSession`.

    Returns:
        tuple: The session and its driver.
    """
    session = ChatSession(**kwargs)
    view    = Driver()
    session.attach(view)
    return session, view


@pytest.fixture
def chat():
    """A session with a driver attached, for the common case."""
    return driven()
