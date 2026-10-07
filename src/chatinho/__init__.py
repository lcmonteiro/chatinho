"""Chatinho: an extensible chat library.

Everyone in a chat is a **peer** with an integer id. ``LOCAL`` — zero — is the
user; connectors are numbered from one. ``TOOL`` — minus one — is the name a
command's messages carry, because a command is not a peer.

A peer is a plain class that declares what it can do. There are three verbs, and
each is a pair: the word you call, and the word the other side writes.

    say(text, reply_to=)   ->  listen(msg)          for everyone but the speaker
    ask(to, text)          ->  answer(msg)          one peer, awaiting its reply
    invoke(name, args)     ->  execute(args, by)    a command run by name

Everything is a coroutine and every peer has its own queue, so a slow subsystem
holds up nobody but itself. ``docs/SPEC.md`` is the reference for all fourteen hooks,
and ``examples/hooks.py`` is that document executable.

Headless — no terminal, and nothing to install beyond this package::

    >>> from chatinho import ChatSession, HelpCommand, require, HookListen
    >>>
    >>> @require(HookListen)
    ... class Printer:
    ...     async def listen(self, msg): print(msg.text)
    >>>
    >>> session = ChatSession(commands=[HelpCommand()])
    >>> at = session.add_connector(Printer())   # doctest: +SKIP

With a terminal, which needs ``pip install chatinho[tui]``::

    >>> from chatinho import build_chat         # doctest: +SKIP
    >>> build_chat(commands=[HelpCommand()]).run()

The application class itself is private: ``build_chat`` builds one.

Six names need an extra, and say so if it is missing:

    build_chat         chatinho[tui]      textual
    OpenAIConnector    chatinho[openai]   openai
    A2AConnector       chatinho[a2a]      requests
    DatabaseBackend    chatinho[sql]      sqlalchemy
    McpFrontend        chatinho[mcp]      mcp
    McpConnector       chatinho[mcp]      mcp

Everything else — ``ChatSession``, the hooks, ``HelpCommand``, ``TestCommand`` —
imports nothing but the standard library.
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:                       # never executed; read by type checkers
    # The six names below are resolved lazily at runtime, which hands a type
    # checker ``Any`` and quietly undoes the ``py.typed`` this package ships.
    # Importing them here restores that without importing anything at run time.
    from .backends import DatabaseBackend
    from .chat_builder import build_chat
    from .connectors.a2a import A2AConnector
    from .connectors.mcp import McpConnector
    from .connectors.openai import OpenAIConnector
    from .frontends.mcp import McpFrontend

from .chat_session import ChatSession
from .chat_message import LOCAL, TOOL, Attachment, ChatMessage, MessageID, Reply, ReplyStatus, Secret
from .chat_hooks import (
    connector,
    tool,
    frontend,
    backend,
    require,
    hooks_of,
    options_of,
    declares,
    declared_id,
    name_of,
    Hook,
    HookSay,
    HookAsk,
    HookAnswer,
    HookInvoke,
    HookExecute,
    HookContext,
    HookPeers,
    HookCommands,
    HookListen,
    HookLoad,
    HookForget,
    HookKeep,
    HookLink,
    HookLocate,
    Say,
    Ask,
    Invoke,
    Context,
    Peers,
    Commands,
    Locate,
)
from .chat_style import ChatStyle
from .commands import HelpCommand, TestCommand

__version__ = "0.1.0"

#: The names that live behind an extra: attribute -> (module, distribution).
_BEHIND_AN_EXTRA = {
    "build_chat"      : (".chat_builder", "tui",    "textual"),
    "OpenAIConnector" : (".connectors.openai", "openai", "openai"),
    "A2AConnector"    : (".connectors.a2a",    "a2a",    "requests"),
    "DatabaseBackend" : (".backends",     "sql",    "sqlalchemy"),
    "McpFrontend"     : (".frontends.mcp",     "mcp",    "mcp"),
    "McpConnector"    : (".connectors.mcp",    "mcp",    "mcp"),
}


def __getattr__(name: str) -> Any:
    """Imports the batteries only when one is asked for (PEP 562).

    ``import chatinho`` must not drag in a terminal, an HTTP client and an ORM
    for a script that wanted a ``ChatSession``. These six are resolved on first
    use instead, and a missing extra is reported as itself rather than as
    somebody else's ``ModuleNotFoundError``.

    Args:
        name: The attribute being read off the package.

    Returns:
        Any: The requested name.

    Raises:
        AttributeError: The package has no such name.
        ImportError: It has, but the extra that carries it is not installed.
    """
    if name not in _BEHIND_AN_EXTRA:
        raise AttributeError("module %r has no attribute %r" % (__name__, name))
    where, extra, needs = _BEHIND_AN_EXTRA[name]
    from importlib import import_module
    try:
        return getattr(import_module(where, __name__), name)
    except ImportError as exc:
        raise ImportError(
            "%s needs %r, which chatinho does not install by default. "
            "Install it with:  pip install 'chatinho[%s]'" % (name, needs, extra)
        ) from exc


def __dir__() -> Any:
    """Keeps tab-completion and ``dir()`` honest about the lazy names."""
    return sorted(__all__)

__all__ = [
    "build_chat",
    "ChatSession",
    "ChatMessage",
    "MessageID",
    "Attachment",
    "Reply",
    "ReplyStatus",
    "Secret",
    "ChatStyle",
    "LOCAL",
    "TOOL",
    # declaring
    "connector",
    "tool",
    "frontend",
    "backend",
    "require",
    "hooks_of",
    "options_of",
    "declares",
    "declared_id",
    "name_of",
    "Hook",
    # the three verbs, and hearing the whole conversation
    "HookSay",
    "HookAsk",
    "HookListen",
    "HookAnswer",
    "HookInvoke",
    "HookExecute",
    "HookContext",
    "HookPeers",
    "HookCommands",
    # the older tier
    "HookLoad",
    "HookForget",
    # what a message carries
    "HookKeep",
    "HookLink",
    "HookLocate",
    # what the grants look like
    "Say",
    "Ask",
    "Invoke",
    "Context",
    "Peers",
    "Commands",
    "Locate",
    # batteries
    "A2AConnector",
    "OpenAIConnector",
    "DatabaseBackend",
    "McpFrontend",
    "McpConnector",
    "HelpCommand",
    "TestCommand",
]
