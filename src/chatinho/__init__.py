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

    >>> from chatinho import build_chat_session     # doctest: +SKIP
    >>> build_chat_session(commands=[HelpCommand()]).run()

Served over MCP, which needs ``pip install chatinho[mcp]``::

    >>> from chatinho import build_mcp_session      # doctest: +SKIP
    >>> build_mcp_session(commands=[HelpCommand()], token="secret").run()

Each builder attaches a frontend — ``ChatFrontend`` or ``McpFrontend``, both in
:mod:`chatinho.frontends` — and either can be passed to ``ChatSession`` by hand.

Nine names need an extra, and say so if it is missing:

    build_chat_session  chatinho[tui,mcp]  textual, fastmcp
    build_mcp_session   chatinho[tui,mcp]  textual, fastmcp
    ChatFrontend        chatinho[tui]      textual
    ChatStyle           chatinho[tui]      textual
    McpFrontend         chatinho[mcp]      fastmcp
    McpConnector        chatinho[mcp]      fastmcp
    OpenAIConnector     chatinho[openai]   openai
    DatabaseBackend     chatinho[sql]      sqlalchemy

Everything else — ``ChatSession``, the hooks, ``HelpCommand``, ``TestCommand`` —
imports nothing but the standard library.
"""

from typing import TYPE_CHECKING, Any, Dict, Tuple

if TYPE_CHECKING:                       # never executed; read by type checkers
    # The names below are resolved lazily at runtime, which hands a type
    # checker ``Any`` and quietly undoes the ``py.typed`` this package ships.
    # Importing them here restores that without importing anything at run time.
    from .backends import DatabaseBackend
    from .builder import build_chat_session, build_mcp_session
    from .connectors.mcp import McpConnector
    from .connectors.openai import OpenAIConnector
    from .frontends.chat import ChatFrontend
    from .frontends.chat.style import ChatStyle
    from .frontends.mcp import McpFrontend

from .session import ChatSession
from .message import LOCAL, TOOL, Attachment, ChatMessage, MessageID, Reply, ReplyStatus, Secret
from .hooks import connector, tool, frontend, backend, require
from .hooks import hooks_of, options_of, declares, declared_id, name_of
from .hooks import Hook, HookSay, HookAsk, HookAnswer, HookInvoke, HookExecute, HookContext
from .hooks import HookPeers, HookCommands, HookListen, HookLoad, HookForget, HookKeep, HookLink, HookLocate
from .hooks import Say, Ask, Invoke, Context, Peers, Commands, Locate
from .commands import HelpCommand, TestCommand

__version__ = "0.1.0"

#: The names that live behind an extra: attribute -> (module, ((extra, library), ...)).
_TUI = ("tui", "textual")
_MCP = ("mcp", "fastmcp")
_BEHIND_AN_EXTRA : Dict[str, Tuple[str, Tuple[Tuple[str, str], ...]]] = {
    "build_chat_session" : (".builder",              (_TUI, _MCP)),
    "build_mcp_session"  : (".builder",              (_TUI, _MCP)),
    "ChatFrontend"       : (".frontends.chat",       (_TUI,)),
    "ChatStyle"          : (".frontends.chat.style", (_TUI,)),
    "McpFrontend"        : (".frontends.mcp",        (_MCP,)),
    "McpConnector"       : (".connectors.mcp",       (_MCP,)),
    "OpenAIConnector"    : (".connectors.openai",    (("openai", "openai"),)),
    "DatabaseBackend"    : (".backends",             (("sql", "sqlalchemy"),)),
}


def __getattr__(name: str) -> Any:
    """Imports the batteries only when one is asked for (PEP 562).

    ``import chatinho`` must not drag in a terminal, an HTTP client and an ORM
    for a script that wanted a ``ChatSession``. These are resolved on first
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
    where, extras = _BEHIND_AN_EXTRA[name]
    from importlib import import_module
    try:
        return getattr(import_module(where, __name__), name)
    except ImportError as exc:
        raise ImportError(
            "%s needs %s, which chatinho does not install by default. "
            "Install it with:  pip install 'chatinho[%s]'" % (
                name,
                " and ".join(repr(library) for _, library in extras),
                ",".join(extra for extra, _ in extras),
            )
        ) from exc


def __dir__() -> Any:
    """Keeps tab-completion and ``dir()`` honest about the lazy names."""
    return sorted(__all__)

__all__ = [
    "build_chat_session",
    "build_mcp_session",
    "ChatSession",
    "ChatMessage",
    "MessageID",
    "Attachment",
    "Reply",
    "ReplyStatus",
    "Secret",
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
    "OpenAIConnector",
    "DatabaseBackend",
    "ChatFrontend",
    "ChatStyle",
    "McpFrontend",
    "McpConnector",
    "HelpCommand",
    "TestCommand",
]
