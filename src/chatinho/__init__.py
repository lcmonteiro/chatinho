"""Chatinho: a extensible chat client library.

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
"""

from .chat import create_chat, Chat
from .connectors import A2AConnector, OpenAIConnector, BaseConnector
from .backends import DatabaseBackend, BaseBackend
from .commands import HelpCommand, TestCommand, BaseCommand

__all__ = [
    "create_chat",
    "Chat",
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

# Keep backward compatibility
from .chat_app import ChatApp, ChatMessage
from .chat_style import ChatStyle

__all__.extend(["ChatApp", "ChatMessage", "ChatStyle"])