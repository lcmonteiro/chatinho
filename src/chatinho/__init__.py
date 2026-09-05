"""Chatinho: an extensible chat client library.

Everyone in a chat is a **participant** with an integer id. ``LOCAL`` — zero —
is the user; connectors and tools are numbered from one. A participant is a
plain class that declares what it can do, and there are only three verbs:

    say(text)          a message for everyone
    ask(to, text)      a message for one participant, awaiting its reply
    answer(msg, text)  the reply that ask is waiting on

A command is an ask addressed to a tool: typing ``/help`` asks the participant
named "help". Everything is a coroutine and every participant has its own
queue, so a slow subsystem holds up nobody but itself.

Example:
    >>> from chatinho import create_chat, HelpCommand
    >>> from chatinho.connectors import OpenAIConnector
    >>> from chatinho.backends import DatabaseBackend
    >>>
    >>> chat = create_chat(
    ...     participants = [OpenAIConnector(name="gpt", api_key="***"), HelpCommand()],
    ...     backend      = DatabaseBackend("sqlite:///my_database.db"),
    ... )
    >>> chat.run()

The application class itself is private: build one with ``create_chat``. For a
chat without a terminal — a script, a bot, a test — use ``ChatSession``
directly and attach your own presentation; it imports no UI framework.
"""

from .chat_app import create_chat
from .chat_session import ChatSession
from .chat_message import LOCAL, ChatMessage
from .chat_hooks import (
    connector,
    tool,
    backend,
    require,
    hooks_of,
    options_of,
    declares,
    name_of,
    Hook,
    HookSay,
    HookAsk,
    HookOnSay,
    HookOnAsk,
    HookContext,
    HookParticipants,
    HookListen,
    HookLoad,
    HookForget,
    Say,
    Ask,
    Answer,
    Context,
    Participants,
)
from .chat_style import ChatStyle
from .connectors import A2AConnector, OpenAIConnector
from .backends import DatabaseBackend
from .commands import HelpCommand, TestCommand

__version__ = "0.1.0"

__all__ = [
    "create_chat",
    "ChatSession",
    "ChatMessage",
    "ChatStyle",
    "LOCAL",
    # declaring
    "connector",
    "tool",
    "backend",
    "require",
    "hooks_of",
    "options_of",
    "declares",
    "name_of",
    "Hook",
    # the three verbs and the two ways of being told
    "HookSay",
    "HookAsk",
    "HookOnSay",
    "HookOnAsk",
    "HookContext",
    "HookParticipants",
    # the older tier
    "HookListen",
    "HookLoad",
    "HookForget",
    # what the grants look like
    "Say",
    "Ask",
    "Answer",
    "Context",
    "Participants",
    # batteries
    "A2AConnector",
    "OpenAIConnector",
    "DatabaseBackend",
    "HelpCommand",
    "TestCommand",
]
