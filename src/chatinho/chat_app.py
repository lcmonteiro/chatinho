"""Chat application: Textual UI wired to connectors, commands and a backend.

The public entry point is :func:`create_chat`, which returns a ready-to-run
application. The class itself (``_Chat``) is private on purpose: build one
through the factory rather than instantiating it directly.

The application owns the wiring; the parts live next door:

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
from .chat_hooks import (
    HOOK_BACKEND_LOAD,
    HOOK_BACKEND_SAVE,
    HOOK_COMMAND_EXECUTED,
    HOOK_CONNECTOR_ADDED,
    HOOK_MESSAGE_RECEIVED,
    HOOK_MESSAGE_SENT,
    HookRegistry,
)
from .chat_input import COMMAND_PREFIX, SUGGESTIONS_ID, CommandInput, CommandSuggestions
from .chat_log import ChatLog
from .chat_message import ChatMessage, MessageStore
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
        connectors      = connectors,
        commands        = commands,
        backend         = backend,
        title           = title,
        welcome_message = welcome_message,
        command_handler = command_handler,
        max_displayed   = max_displayed,
        style           = style,
    )


class _Chat(App):
    """Terminal chat application built with Textual.

    Build instances with :func:`create_chat` rather than directly.

    ``max_displayed`` limits how many messages are rendered in the
    terminal (sliding window). The full history is always kept in
    ``messages`` — older messages only leave the screen, not memory.
    """

    # Default stylesheet, rendered from ChatStyle() at class definition time.
    CSS = ChatStyle().to_css()

    def __init__(
        self,
        connectors      : Optional[List[BaseConnector]] = None,
        commands        : Optional[Dict[str, BaseCommand]] = None,
        backend         : Optional[BaseBackend] = None,
        title           : str = "Chatinho",
        welcome_message : str = "",
        command_handler : Optional[Callable[[str], None]] = None,
        max_displayed   : int = 100,
        style           : Optional[ChatStyle] = None,
    ) -> None:
        super().__init__()
        if style is not None:
            # Instance-level override: Textual reads ``self.CSS`` at mount.
            self.CSS = style.to_css()  # type: ignore[misc]

        # Components
        self.connectors : Dict[str, BaseConnector] = {}
        self.commands   : Dict[str, BaseCommand] = dict(commands) if commands else {}
        self.backend    : Optional[BaseBackend] = backend
        self.command_handler : Optional[Callable[[str], None]] = command_handler
        self.title      = title
        self.welcome_message = welcome_message

        self._store : MessageStore = MessageStore()
        self._hooks : HookRegistry = HookRegistry()

        self._input_placeholder = "Type a message or /command"
        self.max_displayed : int = max_displayed
        # Thread id of the app's main loop (set in on_mount)
        self._app_thread_id : Optional[int] = None

        for connector in connectors or []:
            self.add_connector(connector)
        if self.backend is not None:
            self.backend.initialize()

        logger.info(
            "Chat initialized with %d connector(s), %d command(s) and %s backend",
            len(self.connectors), len(self.commands), type(backend).__name__,
        )

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Container(
            ChatLog(
                self._store,
                max_displayed=self.max_displayed,
                on_reply_target_change=self._on_reply_target_change,
                id=CHAT_LOG_ID,
            ),
            Vertical(
                CommandSuggestions(self.commands, id=SUGGESTIONS_ID),
                CommandInput(placeholder=self._input_placeholder, id=INPUT_ID),
                id="input-area",
            ),
        )

    def on_mount(self) -> None:
        """Focus the input and show the welcome message when the app starts."""
        self._app_thread_id = threading.get_ident()
        self.query_one(f"#{INPUT_ID}", Input).focus()
        if self._store.messages:
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

    # === Public API =================================================================

    @property
    def messages(self) -> List[ChatMessage]:
        """The full message history, oldest first."""
        return self._store.messages

    def send_message(self, text: str, *, reply_to: Optional[str] = None) -> str:
        """Sends a normal message and returns its id.

        Args:
        text : Message content.
        reply_to : Id of the message this one replies to (optional).
        """
        msg = self._store.add(ChatMessage(
            id=self._store.new_id(),
            text=text,
            is_command=False,
            is_sent_by_me=True,
            reply_to=reply_to,
        ))
        self._repaint()
        self.on_message_sent(msg)
        self._hooks.trigger(HOOK_MESSAGE_SENT, msg=msg)
        return msg.id

    def send_command(self, command: str) -> str:
        """Sends a command (without the '/' prefix) and returns its id."""
        logger.info("Command executed: %s", command)
        msg = self._store.add(ChatMessage(
            id=self._store.new_id(),
            text=command,
            is_command=True,
            is_sent_by_me=True,
        ))
        self._repaint()
        self.on_command(command)
        self.on_message_sent(msg)
        self._hooks.trigger(HOOK_MESSAGE_SENT, msg=msg)
        return msg.id

    def receive_message(self, text: str, *, reply_to: Optional[str] = None) -> str:
        """Receives a message from outside and returns its id.

        Safe to call from any thread: if called off the app's main
        thread, UI updates are marshalled via ``call_from_thread``.

        Args:
        text : Message content.
        reply_to : Id of a sent message this one replies to (optional).
        """
        msg = self._store.add(ChatMessage(
            id=self._store.new_id(),
            text=text,
            is_command=False,
            is_sent_by_me=False,
            reply_to=reply_to,
        ))
        self._repaint()
        self.on_message_received(msg)
        self._hooks.trigger(HOOK_MESSAGE_RECEIVED, msg=msg)
        return msg.id

    def get_replies(self, msg_id: str) -> List[str]:
        """Returns the ids of the messages that reply to *msg_id*."""
        return self._store.replies(msg_id)

    def send_pending_reply(self, text: str) -> Optional[str]:
        """Sends *text* as a reply to the selected message (if any).

        Clears the selection. Returns the id of the sent message, or None
        if there is no selected target.
        """
        target = self._reply_target
        if target is None:
            return None
        self._clear_reply_target()
        return self.send_message(text, reply_to=target)

    def add_connector(self, connector: BaseConnector) -> None:
        """Registers *connector*, initializes it and registers its hooks.

        Args:
            connector: The connector to add.
        """
        previous = self.connectors.get(connector.name)
        if previous is not None:
            # Drop the replaced connector's hooks, otherwise it keeps being called
            # (and re-adding the same object would register it twice).
            logger.info("Replacing connector %r", connector.name)
            self._hooks.unregister(previous)

        self.connectors[connector.name] = connector
        self._hooks.register(connector)
        connector.initialize()
        self._hooks.trigger(HOOK_CONNECTOR_ADDED, connector=connector)

    def send_message_via_connector(self, connector_name: str, message: str, **kwargs) -> Any:
        """Sends a message through a specific connector.

        Args:
            connector_name: Name of a registered connector.
            message: The message to send.
            **kwargs: Forwarded to the connector's ``send``.

        Returns:
            Any: Whatever the connector's ``send`` returns.

        Raises:
            ValueError: If no connector is registered under that name.
        """
        if connector_name not in self.connectors:
            raise ValueError("Connector '%s' not found" % connector_name)
        return self.connectors[connector_name].send(message, **kwargs)

    def execute_command(self, command_name: str, *args, **kwargs) -> Any:
        """Executes a registered command and triggers the command hook.

        Args:
            command_name: Name of a registered command.
            *args: Forwarded to the command's ``execute``.
            **kwargs: Forwarded to the command's ``execute``.

        Returns:
            Any: Whatever the command's ``execute`` returns.

        Raises:
            ValueError: If no command is registered under that name.
        """
        if command_name not in self.commands:
            raise ValueError("Command '%s' not found" % command_name)

        try:
            result = self.commands[command_name].execute(*args, **kwargs)
        except Exception as exc:
            logger.error("Error executing command '%s': %s", command_name, exc)
            # Both paths carry the same keys, so a handler declaring
            # (command, result, error) is called on failure too.
            self._hooks.trigger(HOOK_COMMAND_EXECUTED, command=command_name, result=None, error=exc)
            raise
        self._hooks.trigger(HOOK_COMMAND_EXECUTED, command=command_name, result=result, error=None)
        return result

    def save_data(self, key: str, data: Any) -> bool:
        """Saves data through the backend and triggers the save hook.

        Args:
            key: Identifier for the data.
            data: Data to save.

        Returns:
            bool: True if the backend stored the data, False otherwise.

        Raises:
            RuntimeError: If the chat was created without a backend.
        """
        if self.backend is None:
            raise RuntimeError("No backend configured")
        saved = self.backend.save(key, data)
        self._hooks.trigger(HOOK_BACKEND_SAVE, key=key, data=data)
        return saved

    def load_data(self, key: str) -> Any:
        """Loads data through the backend and triggers the load hook.

        Args:
            key: Identifier for the data.

        Returns:
            Any: The stored data, or None if the key is unknown.

        Raises:
            RuntimeError: If the chat was created without a backend.
        """
        if self.backend is None:
            raise RuntimeError("No backend configured")
        data = self.backend.load(key)
        self._hooks.trigger(HOOK_BACKEND_LOAD, key=key, data=data)
        return data

    def delete_data(self, key: str) -> bool:
        """Deletes data through the backend.

        Args:
            key: Identifier for the data.

        Returns:
            bool: True if the backend deleted the data, False otherwise.

        Raises:
            RuntimeError: If the chat was created without a backend.
        """
        if self.backend is None:
            raise RuntimeError("No backend configured")
        return self.backend.delete(key)

    def has_command_suggestions(self) -> bool:
        """Whether the command-suggestion popup currently has entries."""
        return self.query_one(f"#{SUGGESTIONS_ID}", CommandSuggestions).has_suggestions

    # === Hooks (callbacks — all start with ``on_``) ==============================

    def on_command(self, command: str) -> None:
        """Called when the user sends a command (without the '/' prefix).

        Registered commands are executed and their result is displayed as an
        incoming message. Anything else falls through to the ``command_handler``
        callback passed to :func:`create_chat`.
        """
        name, _, arguments = command.strip().partition(" ")
        if name in self.commands:
            try:
                result = self.execute_command(name, chat_instance=self, args=arguments)
            except Exception as exc:  # a broken command must not kill the UI
                self.receive_message("Command `/%s` failed: %s" % (name, exc))
                return
            if result is not None:
                self.receive_message(str(result))
            return
        if self.command_handler is not None:
            self.command_handler(command)

    def on_message_sent(self, msg: ChatMessage) -> None:
        """Called after sending a message (normal or command).

        Useful for hooking the send to a transport (WebSocket, API, …).
        """

    def on_message_received(self, msg: ChatMessage) -> None:
        """Called after receiving a message from outside."""

    # === Internals ==================================================================

    @property
    def _chat_log(self) -> ChatLog:
        """The log widget that renders the store."""
        return self.query_one(f"#{CHAT_LOG_ID}", ChatLog)

    def _repaint(self) -> None:
        """Renders the store's window, marshalling onto the app thread if needed.

        Before ``on_mount`` there is no widget tree yet: the messages stay in
        the store and are painted when the app mounts.
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

    # Thin delegates: the state lives in the store and the log widget.

    def _new_id(self) -> str:
        return self._store.new_id()

    def _find_message(self, msg_id: str) -> Optional[ChatMessage]:
        return self._store.find(msg_id)

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
