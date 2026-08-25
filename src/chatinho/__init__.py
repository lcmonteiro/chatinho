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
"""

from .chat_app import create_chat, ChatMessage
from .chat_style import ChatStyle
from .connectors import A2AConnector, OpenAIConnector, BaseConnector
from .backends import DatabaseBackend, BaseBackend
from .commands import HelpCommand, TestCommand, BaseCommand

__all__ = [
    "create_chat",
    "ChatMessage",
    "ChatStyle",
    # Connectors
    "BaseConnector",
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
