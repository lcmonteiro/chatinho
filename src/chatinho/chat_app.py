"""Textual presentation layer for a :class:`~chatinho.chat_session.ChatSession`.

The public entry point is :func:`create_chat`, which returns a ready-to-run
application. The class itself (``_Chat``) is private on purpose: build one
through the factory rather than instantiating it directly.

This module is the *only* place that knows the chat is a terminal app. It owns
the widget tree, the reply target (a click is a UI concept), thread marshalling
and the welcome message; every use case lives in the session it wraps. The
methods below that mirror the session's are delegates kept for convenience, so
callers can treat the app as the chat.

The parts live next door:

- :mod:`chatinho.chat_session` — the use cases; imports no UI framework.
- :mod:`chatinho.chat_message` — the message model and the history store.
- :mod:`chatinho.chat_hooks`   — the hook constants, decorator and registry.
- :mod:`chatinho.chat_log`     — the scrollable log widget and its bubbles.
- :mod:`chatinho.chat_input`   — the input line and its autocomplete popup.

The library is transport-agnostic: call ``receive_message`` from a worker,
thread, or network callback to inject incoming messages.
"""

import logging
import threading
from typing import Any, Callable, Dict, List, Optional

from textual.app import App, ComposeResult
from textual.containers import Container, Vertical
from textual.widgets import Input

from .backends import BaseBackend
from .chat_input import COMMAND_PREFIX, SUGGESTIONS_ID, CommandInput, CommandSuggestions
from .chat_log import ChatLog
from .chat_message import ChatMessage
from .chat_session import ChatSession
from .chat_style import ChatStyle
from .commands import BaseCommand
from .connectors import BaseConnector

logger = logging.getLogger(__name__)

CHAT_LOG_ID : str = "chat-log"
INPUT_ID    : str = "input-line"


def create_chat(
    connectors      : Optional[List[BaseConnector]] = None,
    commands        : Optional[Dict[str, BaseCommand]] = None,
    backend         : Optional[BaseBackend] = None,
    title           : str = "Chatinho",
    welcome_message : str = "",
    command_handler : Optional[Callable[[str], None]] = None,
    max_displayed   : int = 100,
    style           : Optional[ChatStyle] = None,
) -> "_Chat":
    """Create a chat application from connectors, commands and a backend.

    For a chat without a terminal — a script, a bot, a test — build a
    :class:`~chatinho.chat_session.ChatSession` directly instead.

    Args:
        connectors: Connectors used to talk to external services.
        commands: Commands available as ``/name``, keyed by name.
        backend: Backend used by ``save_data``/``load_data``.
        title: Title of the chat application.
        welcome_message: Message displayed on mount; empty means none.
        command_handler: Called for commands that are not registered in *commands*.
        max_displayed: How many messages are rendered at once (sliding window).
        style: Colour scheme; defaults to :class:`~chatinho.chat_style.ChatStyle`.

    Returns:
        _Chat: The configured application; call ``run()`` to start it.
    """
    return _Chat(
        session         = ChatSession(
            connectors      = connectors,
            commands        = commands,
            backend         = backend,
            command_handler = command_handler,
        ),
        title           = title,
        welcome_message = welcome_message,
        max_displayed   = max_displayed,
        style           = style,
    )


class _Chat(App):
    """Terminal presentation of a :class:`~chatinho.chat_session.ChatSession`.

    Build instances with :func:`create_chat` rather than directly.

    ``max_displayed`` limits how many messages are rendered in the
    terminal (sliding window). The full history is always kept in
    ``messages`` — older messages only leave the screen, not memory.
    """

    # Default stylesheet, rendered from ChatStyle() at class definition time.
    CSS = ChatStyle().to_css()

    def __init__(
        self,
        session         : Optional[ChatSession] = None,
        title           : str = "Chatinho",
        welcome_message : str = "",
        max_displayed   : int = 100,
        style           : Optional[ChatStyle] = None,
    ) -> None:
        super().__init__()
        if style is not None:
            # Instance-level override: Textual reads ``self.CSS`` at mount.
            self.CSS = style.to_css()  # type: ignore[misc]

        self.session : ChatSession = session if session is not None else ChatSession()
        self.title   = title
        self.welcome_message = welcome_message

        # Attach as the session's presentation layer. The lambdas resolve the
        # attribute at call time, so assigning app.on_message_sent = ... after
        # construction still overrides the hook.
        self.session.on_message_added    = lambda msg: self._repaint()
        self.session.on_message_sent     = lambda msg: self.on_message_sent(msg)
        self.session.on_message_received = lambda msg: self.on_message_received(msg)
        self.session.on_command          = lambda command: self.on_command(command)

        self._input_placeholder = "Type a message or /command"
        self.max_displayed : int = max_displayed
        # Thread id of the app's main loop (set in on_mount)
        self._app_thread_id : Optional[int] = None

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Container(
            ChatLog(
                self.session.store,
                max_displayed=self.max_displayed,
                on_reply_target_change=self._on_reply_target_change,
                id=CHAT_LOG_ID,
            ),
            Vertical(
                CommandSuggestions(self.session.commands, id=SUGGESTIONS_ID),
                CommandInput(placeholder=self._input_placeholder, id=INPUT_ID),
                id="input-area",
            ),
        )

    def on_mount(self) -> None:
        """Focus the input and show the welcome message when the app starts."""
        self._app_thread_id = threading.get_ident()
        self.query_one(f"#{INPUT_ID}", Input).focus()
        if self.session.messages:
            # Messages added before the app was mounted (see _repaint)
            self._chat_log.sync()
            self._chat_log.scroll_to_bottom()
        if self.welcome_message:
            self.receive_message(self.welcome_message)

    def on_input_submitted(self, message: Input.Submitted) -> None:
        """Handle user pressing Enter in the input field."""
        del message
        inp = self.query_one(f"#{INPUT_ID}", Input)
        text = inp.value.strip()
        if not text:
            return
        inp.value = ""  # clear input
        if text.startswith(COMMAND_PREFIX):
            self.send_command(text[1:].strip())
        else:
            if self._reply_target is not None:
                self.send_message(text, reply_to=self._reply_target)
                self._clear_reply_target()
            else:
                self.send_message(text)

    def on_input_changed(self, message: Input.Changed) -> None:
        """Update the command-suggestion popup as the user types."""
        if message.input.id != INPUT_ID:
            return
        self.query_one(f"#{SUGGESTIONS_ID}", CommandSuggestions).update_for(message.value)

    # === Presentation-owned behaviour ===============================================

    def send_pending_reply(self, text: str) -> Optional[str]:
        """Sends *text* as a reply to the selected message (if any).

        The reply target is a UI concept — it comes from a click — so this
        lives here rather than in the session.

        Clears the selection. Returns the id of the sent message, or None
        if there is no selected target.
        """
        target = self._reply_target
        if target is None:
            return None
        self._clear_reply_target()
        return self.send_message(text, reply_to=target)

    def has_command_suggestions(self) -> bool:
        """Whether the command-suggestion popup currently has entries."""
        return self.query_one(f"#{SUGGESTIONS_ID}", CommandSuggestions).has_suggestions

    # === Hooks (callbacks — all start with ``on_``) ==============================

    def on_command(self, command: str) -> None:
        """Called when the user sends a command (without the '/' prefix).

        Delegates to the session's dispatch: registered commands are executed
        and their result displayed, anything else falls through to the
        ``command_handler`` passed to :func:`create_chat`. Override to replace
        that behaviour entirely.
        """
        self.session.dispatch_command(command)

    def on_message_sent(self, msg: ChatMessage) -> None:
        """Called after sending a message (normal or command).

        Useful for hooking the send to a transport (WebSocket, API, …).
        """

    def on_message_received(self, msg: ChatMessage) -> None:
        """Called after receiving a message from outside."""

    # === Session delegates ==========================================================

    @property
    def connectors(self) -> Dict[str, BaseConnector]:
        """The session's registered connectors, keyed by name."""
        return self.session.connectors

    @property
    def commands(self) -> Dict[str, BaseCommand]:
        """The session's registered commands, keyed by name."""
        return self.session.commands

    @property
    def backend(self) -> Optional[BaseBackend]:
        """The session's backend, if one was configured."""
        return self.session.backend

    @property
    def command_handler(self) -> Optional[Callable[[str], None]]:
        """The fallback called for unregistered commands."""
        return self.session.command_handler

    @property
    def messages(self) -> List[ChatMessage]:
        """The full message history, oldest first."""
        return self.session.messages

    def send_message(self, text: str, *, reply_to: Optional[str] = None) -> str:
        """Sends a normal message and returns its id."""
        return self.session.send_message(text, reply_to=reply_to)

    def send_command(self, command: str) -> str:
        """Sends a command (without the '/' prefix) and returns its id."""
        return self.session.send_command(command)

    def receive_message(self, text: str, *, reply_to: Optional[str] = None) -> str:
        """Receives a message from outside and returns its id.

        Safe to call from any thread: if called off the app's main thread the
        repaint is marshalled via ``call_from_thread`` (see :meth:`_repaint`).
        """
        return self.session.receive_message(text, reply_to=reply_to)

    def get_replies(self, msg_id: str) -> List[str]:
        """Returns the ids of the messages that reply to *msg_id*."""
        return self.session.get_replies(msg_id)

    def add_connector(self, connector: BaseConnector) -> None:
        """Registers *connector*, initializes it and registers its hooks."""
        self.session.add_connector(connector)

    def send_message_via_connector(self, connector_name: str, message: str, **kwargs) -> Any:
        """Sends a message through a specific connector."""
        return self.session.send_via_connector(connector_name, message, **kwargs)

    def execute_command(self, command_name: str, *args, **kwargs) -> Any:
        """Executes a registered command and triggers the command hook."""
        return self.session.execute_command(command_name, *args, **kwargs)

    def save_data(self, key: str, data: Any) -> bool:
        """Saves data through the backend and triggers the save hook."""
        return self.session.save_data(key, data)

    def load_data(self, key: str) -> Any:
        """Loads data through the backend and triggers the load hook."""
        return self.session.load_data(key)

    def delete_data(self, key: str) -> bool:
        """Deletes data through the backend."""
        return self.session.delete_data(key)

    # === Internals ==================================================================

    @property
    def _chat_log(self) -> ChatLog:
        """The log widget that renders the store."""
        return self.query_one(f"#{CHAT_LOG_ID}", ChatLog)

    def _repaint(self) -> None:
        """Renders the store's window, marshalling onto the app thread if needed.

        Before ``on_mount`` there is no widget tree yet: the messages stay in
        the session and are painted when the app mounts.
        """
        if self._app_thread_id is None:
            return
        if threading.get_ident() == self._app_thread_id:
            self._chat_log.sync()
        else:
            # Off the app thread: marshal the UI update onto the main loop.
            self.call_from_thread(self._chat_log.sync)

    def _on_reply_target_change(self, msg_id: Optional[str]) -> None:
        """Keeps the input placeholder in step with the log's reply target."""
        inp = self.query_one(f"#{INPUT_ID}", Input)
        inp.placeholder = self._input_placeholder if msg_id is None else f"Reply to {msg_id}…"

    # Thin delegates: the state lives in the session and the log widget.

    def _new_id(self) -> str:
        return self.session.new_id()

    def _find_message(self, msg_id: str) -> Optional[ChatMessage]:
        return self.session.find_message(msg_id)

    @property
    def _reply_target(self) -> Optional[str]:
        return self._chat_log.reply_target

    @property
    def _rendered_msg_ids(self) -> List[str]:
        return self._chat_log._rendered_msg_ids

    def _set_reply_target(self, msg_id: str) -> None:
        self._chat_log.set_reply_target(msg_id)

    def _clear_reply_target(self) -> None:
        self._chat_log.clear_reply_target()
