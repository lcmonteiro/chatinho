"""Chatinho: an extensible chat client library.

Example:
    >>> from chatinho import create_chat
    >>> from chatinho.connectors import A2AConnector, OpenAIConnector
    >>> from chatinho.backends import DatabaseBackend
    >>> from chatinho.commands import HelpCommand, TestCommand
    >>>
    >>> chat = create_chat(
    ...     connectors=[
    ...         A2AConnector(
    ...             name="my_connector",
    ...             url="https://api.example.com",
    ...             api_key="***"
    ...         ),
    ...         OpenAIConnector(
    ...             name="openai_connector",
    ...             api_key="***"
    ...         )
    ...     ],
    ...     commands=dict(
    ...         help=HelpCommand(),
    ...         test=TestCommand()
    ...     ),
    ...     backend=DatabaseBackend("sqlite:///my_database.db")
    ... )
    >>> chat.run()

The application class itself is private: build one with ``create_chat``.
For a chat without a terminal — a script, a bot, a test — use ``ChatSession``
directly; it holds the same use cases and imports no UI framework.
"""

from .chat_app import create_chat
from .chat_session import ChatSession
from .chat_message import ChatMessage
from .chat_hooks import (
    hook_point,
    HOOK_MESSAGE_SENT,
    HOOK_MESSAGE_RECEIVED,
    HOOK_COMMAND_EXECUTED,
    HOOK_CONNECTOR_ADDED,
    HOOK_BACKEND_SAVE,
    HOOK_BACKEND_LOAD,
)
from .chat_style import ChatStyle
from .connectors import A2AConnector, OpenAIConnector, BaseConnector, BidirectionalConnector
from .backends import DatabaseBackend, BaseBackend
from .commands import HelpCommand, TestCommand, BaseCommand

__all__ = [
    "create_chat",
    "ChatSession",
    "ChatMessage",
    "ChatStyle",
    # Connector hook system
    "hook_point",
    "HOOK_MESSAGE_SENT",
    "HOOK_MESSAGE_RECEIVED",
    "HOOK_COMMAND_EXECUTED",
    "HOOK_CONNECTOR_ADDED",
    "HOOK_BACKEND_SAVE",
    "HOOK_BACKEND_LOAD",
    # Connectors
    "BaseConnector",
    "BidirectionalConnector",
    "A2AConnector",
    "OpenAIConnector",
    # Backends
    "BaseBackend",
    "DatabaseBackend",
    # Commands
    "BaseCommand",
    "HelpCommand",
    "TestCommand",
]
