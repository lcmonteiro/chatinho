"""Chat application: Textual UI wired to connectors, commands and a backend.

The public entry point is :func:`create_chat`, which returns a ready-to-run
application. The class itself (``_Chat``) is private on purpose: build one
through the factory rather than instantiating it directly.

Features:
- Message display with Markdown rendering and syntax highlighting for code blocks.
- Input field for sending messages and commands (starting with '/'), with an
  autocomplete popup fed by the registered commands.
- Ability to tag outgoing messages with an ID and match incoming replies.
- Simple in-memory message history.
- A hook system where connectors opt into events via the ``@hook_point`` decorator.

The library is transport-agnostic: call ``receive_message`` from a worker,
thread, or network callback to inject incoming messages.
"""

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple, cast

from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, ScrollableContainer, Vertical
from textual.widget import Widget
from textual.widgets import Input, Markdown, OptionList, Static
from textual.widgets.option_list import Option

from .backends import BaseBackend
from .chat_style import ChatStyle
from .commands import BaseCommand
from .connectors import BaseConnector

logger = logging.getLogger(__name__)

COMMAND_PREFIX : str = "/"


# === Hook system ================================================================

HOOK_MESSAGE_SENT     : str = "message_sent"
HOOK_MESSAGE_RECEIVED : str = "message_received"
HOOK_COMMAND_EXECUTED : str = "command_executed"
HOOK_CONNECTOR_ADDED  : str = "connector_added"
HOOK_BACKEND_SAVE     : str = "backend_save"
HOOK_BACKEND_LOAD     : str = "backend_load"

# Hook name -> the connector method called when the hook fires.
HOOK_METHODS : Dict[str, str] = {
    HOOK_MESSAGE_SENT     : "on_message_sent",
    HOOK_MESSAGE_RECEIVED : "on_message_received",
    HOOK_COMMAND_EXECUTED : "on_command_executed",
    HOOK_CONNECTOR_ADDED  : "on_connector_added",
    HOOK_BACKEND_SAVE     : "on_backend_save",
    HOOK_BACKEND_LOAD     : "on_backend_load",
}

ALL_HOOKS = frozenset(HOOK_METHODS)


def hook_point(*event_names: str) -> Callable[[type], type]:
    """Declare which hook points a connector class handles.

    Only connectors decorated with the hook they care about are called; the
    matching ``on_*`` method receives that hook's payload as keyword arguments:

    ==========================  ======================  ==========================
    hook                        method                  payload
    ==========================  ======================  ==========================
    HOOK_MESSAGE_SENT           on_message_sent         msg
    HOOK_MESSAGE_RECEIVED       on_message_received     msg
    HOOK_COMMAND_EXECUTED       on_command_executed     command, result, error
    HOOK_CONNECTOR_ADDED        on_connector_added      connector
    HOOK_BACKEND_SAVE           on_backend_save         key, data
    HOOK_BACKEND_LOAD           on_backend_load         key, data
    ==========================  ======================  ==========================

    ``on_command_executed`` is called on both paths: on failure ``result`` is
    None and ``error`` carries the exception, on success ``error`` is None.
    Accept ``**kwargs`` so new payload keys do not break existing connectors.

    Usage:
        @hook_point(HOOK_MESSAGE_SENT, HOOK_MESSAGE_RECEIVED)
        class MyConnector(BaseConnector):
            def on_message_sent(self, msg, **kwargs): ...
            def on_message_received(self, msg, **kwargs): ...

    Args:
        *event_names: Hook constants the decorated class handles.

    Returns:
        Callable: The class decorator.
    """
    def decorator(cls: type) -> type:
        points = set(getattr(cls, "_hook_points", ()))
        points.update(event_names)
        cls._hook_points = points  # type: ignore[attr-defined]
        return cls
    return decorator


# === Widgets ====================================================================

class TouchScrollableContainer(ScrollableContainer):
    """Scrollable container that supports mouse/touch drag scrolling."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._drag_start_y: int = 0
        self._scroll_start_y: int = 0

    def on_mouse_down(self, event: events.MouseDown) -> None:
        """Record the start position when drag begins."""
        self._drag_start_y = event.y
        self._scroll_start_y = self.scroll_offset.y
        event.stop()

    def on_mouse_move(self, event: events.MouseMove) -> None:
        """Handle drag to scroll vertically."""
        if not event.button:
            return
        delta_y = event.y - self._drag_start_y
        target_y = self._scroll_start_y - delta_y
        max_y = self.max_scroll_y
        if max_y > 0:
            target_y = max(0, min(target_y, max_y))
            self.scroll_to(y=target_y, animate=False)
        event.stop()

    def on_mouse_up(self, event: events.MouseUp) -> None:
        """Handle drag end."""
        event.stop()


class _MessageContainer(Horizontal):
    """Clickable message container — selects the msg as a reply target."""

    def __init__(
        self,
        *children: Widget,
        msg_id: str,
        on_select: Callable[[str], None],
        **kwargs,
    ) -> None:
        super().__init__(*children, **kwargs)
        self.msg_id = msg_id
        self._on_select = on_select

    def on_click(self, event: events.Click) -> None:
        self._on_select(self.msg_id)
        event.stop()


@dataclass
class ChatMessage:
    """Represents a chat message."""

    id          : str
    text        : str
    timestamp   : datetime = field(default_factory=datetime.now)
    is_command  : bool = False
    reply_to    : Optional[str] = None
    is_sent_by_me : bool = True


# === Public factory =============================================================

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

        # Hook registry: maps hook name to the connectors that declared it
        self._hook_registry : Dict[str, List[BaseConnector]] = {hook: [] for hook in ALL_HOOKS}

        # Message state
        self.messages  : List[ChatMessage] = []
        self._next_id  : int = 1
        self._id_lock  : threading.Lock = threading.Lock()
        # Mapping from message id to list of reply ids (for threading)
        self._replies  : Dict[str, List[str]] = {}
        self._replies_lock : threading.Lock = threading.Lock()
        # Message selected as reply target (via click)
        self._reply_target : Optional[str] = None
        self._msg_widgets  : Dict[str, Widget] = {}
        self._msg_index    : Dict[str, ChatMessage] = {}
        self._input_placeholder = "Type a message or /command"
        # Max number of messages rendered in the terminal (history stays complete in ``messages``)
        self.max_displayed : int = max_displayed
        # IDs of the messages currently rendered, in order
        self._rendered_msg_ids : List[str] = []
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
            TouchScrollableContainer(id="chat-log"),
            Vertical(
                OptionList(id="command-suggestions"),
                _CommandInput(placeholder=self._input_placeholder, id="input-line"),
                id="input-area",
            ),
        )

    def on_mount(self) -> None:
        """Focus the input and show the welcome message when the app starts."""
        self._app_thread_id = threading.get_ident()
        self.query_one("#input-line", Input).focus()
        if self.messages:
            # Messages added before the app was mounted (see _add_message)
            self._refresh_chat_log()
            self._scroll_to_bottom()
        if self.welcome_message:
            self.receive_message(self.welcome_message)

    def on_input_submitted(self, message: Input.Submitted) -> None:
        """Handle user pressing Enter in the input field."""
        del message
        inp = self.query_one("#input-line", Input)
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
        if message.input.id != "input-line":
            return
        self._update_command_suggestions(message.value)

    # === Public API =================================================================

    def send_message(self, text: str, *, reply_to: Optional[str] = None) -> str:
        """Sends a normal message and returns its id.

        Args:
        text : Message content.
        reply_to : Id of the message this one replies to (optional).
        """
        msg = ChatMessage(
            id=self._new_id(),
            text=text,
            is_command=False,
            is_sent_by_me=True,
            reply_to=reply_to,
        )
        self._add_message(msg)
        if reply_to is not None:
            self._record_reply(reply_to, msg.id)
        self.on_message_sent(msg)
        self._trigger_hook(HOOK_MESSAGE_SENT, msg=msg)
        return msg.id

    def send_command(self, command: str) -> str:
        """Sends a command (without the '/' prefix) and returns its id."""
        logger.info("Command executed: %s", command)
        msg = ChatMessage(
            id=self._new_id(),
            text=command,
            is_command=True,
            is_sent_by_me=True,
        )
        self._add_message(msg)
        self.on_command(command)
        self.on_message_sent(msg)
        self._trigger_hook(HOOK_MESSAGE_SENT, msg=msg)
        return msg.id

    def receive_message(
        self,
        text: str,
        *,
        reply_to: Optional[str] = None,
    ) -> str:
        """Receives a message from outside and returns its id.

        Safe to call from any thread: if called off the app's main
        thread, UI updates are marshalled via ``call_from_thread``.

        Args:
        text : Message content.
        reply_to : Id of a sent message this one replies to (optional).
        """
        msg = ChatMessage(
            id=self._new_id(),
            text=text,
            is_command=False,
            is_sent_by_me=False,
            reply_to=reply_to,
        )
        if self._app_thread_id is None or threading.get_ident() == self._app_thread_id:
            # App not mounted yet (history only), or already on the app thread.
            self._add_message(msg)
        else:
            # Off the app thread: marshal the UI update onto the main loop.
            self.call_from_thread(self._add_message, msg)
        if reply_to is not None:
            self._record_reply(reply_to, msg.id)
        self.on_message_received(msg)
        self._trigger_hook(HOOK_MESSAGE_RECEIVED, msg=msg)
        return msg.id

    def get_replies(self, msg_id: str) -> List[str]:
        """Returns the ids of the messages that reply to *msg_id*."""
        with self._replies_lock:
            return list(self._replies.get(msg_id, []))

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
            for registered in self._hook_registry.values():
                registered[:] = [c for c in registered if c is not previous]

        self.connectors[connector.name] = connector
        for hook in getattr(connector, "_hook_points", ()):
            if hook in self._hook_registry:
                self._hook_registry[hook].append(connector)
            else:
                logger.warning("Connector %r declares unknown hook: %s", connector.name, hook)
        connector.initialize()
        self._trigger_hook(HOOK_CONNECTOR_ADDED, connector=connector)

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
            self._trigger_hook(HOOK_COMMAND_EXECUTED, command=command_name, result=None, error=exc)
            raise
        self._trigger_hook(HOOK_COMMAND_EXECUTED, command=command_name, result=result, error=None)
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
        self._trigger_hook(HOOK_BACKEND_SAVE, key=key, data=data)
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
        self._trigger_hook(HOOK_BACKEND_LOAD, key=key, data=data)
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

    def _trigger_hook(self, hook_name: str, **kwargs) -> None:
        """Calls every connector that declared *hook_name* via ``@hook_point``.

        Args:
            hook_name: The hook constant to trigger.
            **kwargs: Payload passed to the connector's hook method.
        """
        method_name = HOOK_METHODS.get(hook_name)
        if method_name is None:
            logger.warning("Unknown hook name: %s", hook_name)
            return

        for connector in self._hook_registry.get(hook_name, []):
            method = getattr(connector, method_name, None)
            if method is None:
                logger.debug("Connector %r does not implement %s", connector.name, method_name)
                continue
            try:
                method(**kwargs)
            except Exception as exc:
                logger.error(
                    "Error in hook '%s' for connector %r: %s", hook_name, connector.name, exc,
                    exc_info=True,
                )

    def _record_reply(self, reply_to: str, msg_id: str) -> None:
        """Thread-safely records that *msg_id* replies to *reply_to*."""
        with self._replies_lock:
            self._replies.setdefault(reply_to, []).append(msg_id)

    def _new_id(self) -> str:
        with self._id_lock:
            msg_id = f"msg-{self._next_id}"
            self._next_id += 1
        return msg_id

    def _add_message(self, msg: ChatMessage) -> str:
        """Adds a message to the history and re-renders the log."""
        self.messages.append(msg)
        self._msg_index[msg.id] = msg
        if self._app_thread_id is None:
            # Before on_mount there is no widget tree to render into; the
            # message is kept in history and painted by on_mount.
            return msg.id
        chat_log = self.query_one("#chat-log", ScrollableContainer)
        # Only auto-scrolls if the user is already at the bottom (otherwise they lose their reading position)
        was_at_bottom = chat_log.scroll_offset.y >= (chat_log.max_scroll_y - 1)
        self._refresh_chat_log()
        if was_at_bottom:
            self._scroll_to_bottom()
        return msg.id

    def _refresh_chat_log(self) -> None:
        """Renders only the last ``max_displayed`` messages (sliding window).

        Mounts the new ones and unmounts the old ones that left the window,
        to limit the number of widgets in the terminal.
        """
        chat_log = self.query_one("#chat-log", ScrollableContainer)

        # Desired window: the last max_displayed messages
        total = len(self.messages)
        start = max(0, total - self.max_displayed)
        desired_ids = [m.id for m in self.messages[start:]]

        current = set(self._rendered_msg_ids)
        desired = set(desired_ids)

        # Unmount messages that left the window
        for msg_id in self._rendered_msg_ids:
            if msg_id not in desired:
                widget = self._msg_widgets.pop(msg_id, None)
                if widget is not None:
                    widget.remove()

        # Mount the new ones, in the correct order
        for msg_id in desired_ids:
            if msg_id not in current:
                msg = self._find_message(msg_id)
                if msg is not None:
                    chat_log.mount(self._render_message(msg))

        self._rendered_msg_ids = desired_ids

    def _render_message(self, msg: ChatMessage) -> Widget:
        """Render a message as a clickable container with header and body."""
        sender = "You" if msg.is_sent_by_me else "Other"
        time_str = msg.timestamp.strftime("%H:%M")
        prefix = f"[{time_str}] {sender} · {msg.id}"
        if msg.reply_to is not None:
            prefix += " ↳ replying"

        header = Static(prefix, classes="message-header")
        parts: List[Widget] = [header]

        # Quote of the original message when this is a reply
        if msg.reply_to is not None:
            original = self._find_message(msg.reply_to)
            if original is not None:
                preview = " ".join(original.text.split())[:60]
                parts.append(
                    Static(f"↳ {original.id}: {preview}…", classes="message-quote")
                )

        parts.append(Markdown(msg.text, classes="message-body"))

        bubble = Vertical(*parts, classes="message-bubble")

        # Clickable container — aligns left/right and selects the reply target
        container = _MessageContainer(
            bubble,
            msg_id=msg.id,
            on_select=self._on_message_clicked,
            classes="message-container",
        )
        if msg.is_sent_by_me:
            container.add_class("sent")
        else:
            container.add_class("received")

        self._msg_widgets[msg.id] = container
        return container

    # === Reply target (click) ======================================================

    def _on_message_clicked(self, msg_id: str) -> None:
        """Selects/deselects a message as the reply target."""
        if self._reply_target == msg_id:
            self._clear_reply_target()
        else:
            self._set_reply_target(msg_id)

    def _set_reply_target(self, msg_id: str) -> None:
        """Marks *msg_id* as the reply target and updates the input."""
        self._reply_target = msg_id
        self._refresh_reply_target_ui()
        inp = self.query_one("#input-line", Input)
        inp.placeholder = f"Reply to {msg_id}…"

    def _clear_reply_target(self) -> None:
        """Clears the reply target and restores the input."""
        self._reply_target = None
        self._refresh_reply_target_ui()
        inp = self.query_one("#input-line", Input)
        inp.placeholder = self._input_placeholder

    def _refresh_reply_target_ui(self) -> None:
        """Updates the visual highlight of all messages."""
        for msg_id, widget in self._msg_widgets.items():
            widget.set_class(msg_id == self._reply_target, "reply-target")

    def send_pending_reply(self, text: str) -> Optional[str]:
        """Sends *text* as a reply to the selected message (if any).

        Clears the selection. Returns the id of the sent message, or None
        if there is no selected target.
        """
        if self._reply_target is None:
            return None
        target = self._reply_target
        self._clear_reply_target()
        return self.send_message(text, reply_to=target)

    # === Command suggestions (autocomplete) ========================================

    def has_command_suggestions(self) -> bool:
        """Whether the command-suggestion popup currently has entries."""
        return self.query_one("#command-suggestions", OptionList).option_count > 0

    def _suggestion_label(self, name: str) -> str:
        """Returns the popup label for the command registered as *name*."""
        description = self.commands[name].description
        if description:
            return f"{COMMAND_PREFIX}{name}  —  {description}"
        return f"{COMMAND_PREFIX}{name}"

    def _update_command_suggestions(self, text: str) -> None:
        """Shows commands matching the "/token" currently being typed."""
        matches: List[str] = []
        if text.startswith(COMMAND_PREFIX) and " " not in text:
            token = text[len(COMMAND_PREFIX):]
            matches = sorted(name for name in self.commands if name.startswith(token))

        suggestions = self.query_one("#command-suggestions", OptionList)
        if not matches:
            self._hide_command_suggestions()
            return

        suggestions.set_options(
            Option(self._suggestion_label(name), id=name) for name in matches
        )
        suggestions.highlighted = 0
        suggestions.add_class("-visible")

    def _hide_command_suggestions(self) -> None:
        """Hides and clears the command-suggestion popup."""
        suggestions = self.query_one("#command-suggestions", OptionList)
        suggestions.remove_class("-visible")
        suggestions.clear_options()

    def _move_command_suggestion(self, delta: int) -> None:
        """Moves the suggestion highlight up (delta<0) or down (delta>0)."""
        suggestions = self.query_one("#command-suggestions", OptionList)
        if delta > 0:
            suggestions.action_cursor_down()
        else:
            suggestions.action_cursor_up()

    def _accept_command_suggestion(self) -> bool:
        """Completes the input with the highlighted suggestion, if any.

        Returns True if a suggestion was accepted.
        """
        suggestions = self.query_one("#command-suggestions", OptionList)
        option = suggestions.highlighted_option
        if option is None or option.id is None:
            return False
        inp = self.query_one("#input-line", Input)
        inp.value = f"{COMMAND_PREFIX}{option.id} "
        inp.action_end()
        self._hide_command_suggestions()
        return True

    def _find_message(self, msg_id: str) -> Optional[ChatMessage]:
        """Returns the message with the given id, or None."""
        return self._msg_index.get(msg_id)

    def _scroll_to_bottom(self) -> None:
        """Scrolls the chat log to the bottom."""
        chat_log = self.query_one("#chat-log", ScrollableContainer)
        chat_log.scroll_end(animate=False)


class _CommandInput(Input):
    """Input that drives the command-suggestion popup owned by :class:`_Chat`.

    Tab/Down/Up/Escape are only claimed while a suggestion popup is open
    (see ``check_action``) — otherwise they fall through to Textual's
    normal bindings (e.g. Tab still moves focus as usual).
    """

    BINDINGS = [
        Binding("tab", "accept_suggestion", show=False),
        Binding("down", "next_suggestion", show=False),
        Binding("up", "prev_suggestion", show=False),
        Binding("escape", "dismiss_suggestions", show=False),
    ]

    def check_action(self, action: str, parameters: Tuple[object, ...]) -> Optional[bool]:
        if action in ("accept_suggestion", "next_suggestion", "prev_suggestion", "dismiss_suggestions"):
            return cast(_Chat, self.app).has_command_suggestions()
        return True

    def action_accept_suggestion(self) -> None:
        cast(_Chat, self.app)._accept_command_suggestion()

    def action_next_suggestion(self) -> None:
        cast(_Chat, self.app)._move_command_suggestion(1)

    def action_prev_suggestion(self) -> None:
        cast(_Chat, self.app)._move_command_suggestion(-1)

    def action_dismiss_suggestions(self) -> None:
        cast(_Chat, self.app)._hide_command_suggestions()

    async def action_submit(self) -> None:
        app = cast(_Chat, self.app)
        if app.has_command_suggestions() and app._accept_command_suggestion():
            return
        await super().action_submit()
