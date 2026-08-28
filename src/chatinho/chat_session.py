"""The chat core: messages, commands, connectors and persistence.

:class:`ChatSession` holds every use case the chat offers and imports no UI
framework, so it can be driven from a TUI, a script or a test without a
terminal. A presentation layer attaches itself through the observer slots
(``on_message_added`` and friends) — the session never reaches out to it.

``title``, ``welcome_message`` and anything about rendering live in the
presentation layer, not here.
"""

import logging
from typing import Any, Callable, Dict, List, Optional

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
from .chat_message import ChatMessage, MessageStore
from .commands import BaseCommand
from .connectors import BaseConnector

logger = logging.getLogger(__name__)

COMMAND_PREFIX : str = "/"


class ChatSession:
    """Orchestrates the message store, the hook registry, commands and a backend.

    Observer slots are plain callables, left as None when nobody is watching:

    - ``on_message_added``    — a message entered the history (repaint here).
    - ``on_message_sent``     — after a message or command was sent.
    - ``on_message_received`` — after a message arrived from outside.
    - ``on_command``          — a command was sent; replaces the default
      dispatch entirely, so an owner that wants both must call
      :meth:`dispatch_command` itself.
    """

    def __init__(
        self,
        connectors      : Optional[List[BaseConnector]] = None,
        commands        : Optional[Dict[str, BaseCommand]] = None,
        backend         : Optional[BaseBackend] = None,
        command_handler : Optional[Callable[[str], None]] = None,
    ) -> None:
        self.connectors : Dict[str, BaseConnector] = {}
        self.commands   : Dict[str, BaseCommand] = dict(commands) if commands else {}
        self.backend    : Optional[BaseBackend] = backend
        self.command_handler : Optional[Callable[[str], None]] = command_handler

        self._store : MessageStore = MessageStore()
        self._hooks : HookRegistry = HookRegistry()

        self.on_message_added    : Optional[Callable[[ChatMessage], None]] = None
        self.on_message_sent     : Optional[Callable[[ChatMessage], None]] = None
        self.on_message_received : Optional[Callable[[ChatMessage], None]] = None
        self.on_command          : Optional[Callable[[str], None]] = None

        for connector in connectors or []:
            self.add_connector(connector)
        if self.backend is not None:
            self.backend.initialize()

        logger.info(
            "Chat session initialized with %d connector(s), %d command(s) and %s backend",
            len(self.connectors), len(self.commands), type(backend).__name__,
        )

    # === Messages ===================================================================

    @property
    def store(self) -> MessageStore:
        """The message history itself.

        Exposed because a view renders the store directly; it is a plain
        domain object with no framework dependency, so handing it to the
        presentation layer costs nothing.
        """
        return self._store

    @property
    def messages(self) -> List[ChatMessage]:
        """The full message history, oldest first."""
        return self._store.messages

    def new_id(self) -> str:
        """Returns a fresh message id. Safe to call from any thread."""
        return self._store.new_id()

    def find_message(self, msg_id: str) -> Optional[ChatMessage]:
        """Returns the message with the given id, or None."""
        return self._store.find(msg_id)

    def get_replies(self, msg_id: str) -> List[str]:
        """Returns the ids of the messages that reply to *msg_id*."""
        return self._store.replies(msg_id)

    def window(self, size: int) -> List[ChatMessage]:
        """Returns the last *size* messages, oldest first."""
        return self._store.window(size)

    def send_message(self, text: str, *, reply_to: Optional[str] = None) -> str:
        """Sends a normal message and returns its id.

        Args:
            text: Message content.
            reply_to: Id of the message this one replies to (optional).

        Returns:
            str: The new message's id.
        """
        msg = self._store.add(ChatMessage(
            id=self._store.new_id(),
            text=text,
            is_command=False,
            is_sent_by_me=True,
            reply_to=reply_to,
        ))
        self._notify(self.on_message_added, msg)
        self._notify(self.on_message_sent, msg)
        self._hooks.trigger(HOOK_MESSAGE_SENT, msg=msg)
        return msg.id

    def send_command(self, command: str) -> str:
        """Sends a command (without the '/' prefix) and returns its id.

        The command is dispatched through ``on_command`` when an owner set it,
        otherwise through :meth:`dispatch_command`.

        Args:
            command: The command line, without the leading prefix.

        Returns:
            str: The new message's id.
        """
        logger.info("Command executed: %s", command)
        msg = self._store.add(ChatMessage(
            id=self._store.new_id(),
            text=command,
            is_command=True,
            is_sent_by_me=True,
        ))
        self._notify(self.on_message_added, msg)
        if self.on_command is not None:
            self.on_command(command)
        else:
            self.dispatch_command(command)
        self._notify(self.on_message_sent, msg)
        self._hooks.trigger(HOOK_MESSAGE_SENT, msg=msg)
        return msg.id

    def receive_message(self, text: str, *, reply_to: Optional[str] = None) -> str:
        """Receives a message from outside and returns its id.

        Args:
            text: Message content.
            reply_to: Id of a sent message this one replies to (optional).

        Returns:
            str: The new message's id.
        """
        msg = self._store.add(ChatMessage(
            id=self._store.new_id(),
            text=text,
            is_command=False,
            is_sent_by_me=False,
            reply_to=reply_to,
        ))
        self._notify(self.on_message_added, msg)
        self._notify(self.on_message_received, msg)
        self._hooks.trigger(HOOK_MESSAGE_RECEIVED, msg=msg)
        return msg.id

    # === Commands ===================================================================

    def dispatch_command(self, command: str) -> None:
        """Runs a registered command and displays its result.

        Registered commands are executed with this session as ``chat_instance``
        and their result is shown as an incoming message. Anything else falls
        through to the ``command_handler`` callback.

        Args:
            command: The command line, without the leading prefix.
        """
        name, _, arguments = command.strip().partition(" ")
        if name in self.commands:
            try:
                result = self.execute_command(name, chat_instance=self, args=arguments)
            except Exception as exc:  # a broken command must not kill its owner
                self.receive_message("Command `%s%s` failed: %s" % (COMMAND_PREFIX, name, exc))
                return
            if result is not None:
                self.receive_message(str(result))
            return
        if self.command_handler is not None:
            self.command_handler(command)

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

    # === Connectors =================================================================

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

    def send_via_connector(self, connector_name: str, message: str, **kwargs) -> Any:
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

    # === Persistence ================================================================

    def save_data(self, key: str, data: Any) -> bool:
        """Saves data through the backend and triggers the save hook.

        Args:
            key: Identifier for the data.
            data: Data to save.

        Returns:
            bool: True if the backend stored the data, False otherwise.

        Raises:
            RuntimeError: If the session was created without a backend.
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
            RuntimeError: If the session was created without a backend.
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
            RuntimeError: If the session was created without a backend.
        """
        if self.backend is None:
            raise RuntimeError("No backend configured")
        return self.backend.delete(key)

    # === Internals ==================================================================

    @staticmethod
    def _notify(observer: Optional[Callable[[Any], None]], payload: Any) -> None:
        """Calls *observer* if an owner attached one."""
        if observer is not None:
            observer(payload)
