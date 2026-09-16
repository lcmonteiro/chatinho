"""Builds a chat: a session, and the terminal attached to it like any peer.

:func:`build_chat` is the public entry point for a chat with a terminal. It
does what a caller would do by hand — build a :class:`~chatinho.chat_session.ChatSession`,
build a :class:`~chatinho.chat_app.ChatApp`, and hand the app to the session
with :meth:`~chatinho.chat_session.ChatSession.add_connector` — because the
terminal is a normal connector now, not something its own constructor wires up.
"""

from typing import Any, List, Optional

from .chat_app import ChatApp
from .chat_session import ChatSession
from .chat_style import ChatStyle


def build_chat(
    connectors      : Optional[List[Any]] = None,
    commands        : Optional[List[Any]] = None,
    backend         : Optional[Any] = None,
    title           : str = "Chatinho",
    welcome_message : str = "",
    max_displayed   : int = 100,
    style           : Optional[ChatStyle] = None,
    quit_key        : str = "ctrl+q",
    copy_key        : str = "ctrl+y",
    name            : Optional[str] = None,
) -> ChatSession:
    """Builds a chat application from peers and a backend.

    A **connector** is a peer: it has an id and a queue, and the conversation
    reaches it. A **command** is not: it has neither, and it runs only when
    someone runs it. They are separate parameters because they are separate
    things.

    For a chat without a terminal — a script, a bot, a test — build a
    :class:`~chatinho.chat_session.ChatSession` directly and attach your own
    presentation.

    Args:
        connectors: Links to agents or APIs; peers, numbered from one.
        commands: Things the user runs as ``/name``; not peers.
        backend: Backend used by ``save_data``/``load_data``.
        title: Title of the chat application.
        welcome_message: Message displayed on mount; empty means none.
        max_displayed: How many messages are rendered at once (sliding window).
        style: Colour scheme; defaults to :class:`~chatinho.chat_style.ChatStyle`.
        copy_key: Copies the message selected as the reply target. Tap a
            message, then press it — the keyboard way in, for a terminal that
            takes the long press for its own menu before the chat sees it.
        name: What the terminal is called in the log, shown as ``@name`` on
            every message the user sends. Defaults to the ``chat`` the class
            declares; ``"me"`` reads better in a chat you are in.
        quit_key: The key that quits, as Textual writes them — ``"ctrl+g"``,
            ``"f10"``, ``"escape"``. Defaults to Textual's own ``"ctrl+q"``,
            which stops quitting when another key is given. ``ctrl+c`` is a
            separate binding and is left alone.

    Returns:
        ChatSession: The session, with the terminal attached at ``LOCAL``. Call
        ``run()`` on it: the session owns the loop, and the terminal is one of
        the peers it serves.

    Raises:
        ValueError: ``quit_key`` is not a key Textual could receive.
    """
    chat_connector = ChatApp(
        title           = title,
        welcome_message = welcome_message,
        max_displayed   = max_displayed,
        style           = style,
        quit_key        = quit_key,
        copy_key        = copy_key,
        name            = name,
    )
    return ChatSession(
        connectors=[chat_connector, *(connectors or [])], 
        commands=commands, 
        backend=backend,
    )
