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

from .chat_hooks import (
    Hook,
    HookAnswer,
    HookDelete,
    HookExecute,
    HookLoad,
    HookSave,
    HookBackendLoad,
    HookBackendSave,
    HookCommandExecuted,
    HookConnectorAdded,
    HookMessageReceived,
    HookMessageSent,
    HookRegistry,
    declares,
    hooks_of,
    name_of,
)
from .chat_hooks import Inbox
from .chat_message import ChatMessage, MessageStore

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
        connectors      : Optional[List[Any]] = None,
        commands        : Optional[List[Any]] = None,
        backend         : Optional[Any] = None,
        command_handler : Optional[Callable[[str], None]] = None,
    ) -> None:
        self.connectors : Dict[str, Any] = {}
        self.commands   : Dict[str, Any] = {}
        self.backend    : Optional[Any] = backend
        self.command_handler : Optional[Callable[[str], None]] = command_handler

        self._store : MessageStore = MessageStore()
        self._hooks : HookRegistry = HookRegistry()

        self.on_message_added    : Optional[Callable[[ChatMessage], None]] = None
        self.on_message_sent     : Optional[Callable[[ChatMessage], None]] = None
        self.on_message_received : Optional[Callable[[ChatMessage], None]] = None
        self.on_command          : Optional[Callable[[str], None]] = None

        for connector in connectors or []:
            self.add_connector(connector)
        for cmd in commands or []:
            self.add_command(cmd)
        if self.backend is not None:
            self._grant(self.backend, name_of(self.backend))
            self._start(self.backend)

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
        self._route_reply(msg)
        self._notify(self.on_message_sent, msg)
        self._hooks.trigger(HookMessageSent, msg=msg)
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
        self._hooks.trigger(HookMessageSent, msg=msg)
        return msg.id

    def receive_message(
        self,
        text: str,
        *,
        reply_to       : Optional[str] = None,
        origin         : Optional[str] = None,
        correlation_id : Optional[str] = None,
    ) -> str:
        """Receives a message from outside and returns its id.

        Args:
            text: Message content.
            reply_to: Id of a sent message this one replies to (optional).
            origin: Name of the connector it arrived through, when it did.
            correlation_id: The far side's id for the exchange; replying to
                this message sends the reply back through *origin*.

        Returns:
            str: The new message's id.
        """
        msg = self._store.add(ChatMessage(
            id=self._store.new_id(),
            text=text,
            is_command=False,
            is_sent_by_me=False,
            reply_to=reply_to,
            origin=origin,
            correlation_id=correlation_id,
        ))
        self._notify(self.on_message_added, msg)
        self._notify(self.on_message_received, msg)
        self._hooks.trigger(HookMessageReceived, msg=msg)
        return msg.id

    def deliver(
        self,
        connector_name : str,
        text           : str,
        correlation_id : Optional[str] = None,
    ) -> str:
        """Puts a question that arrived through a connector in front of the user.

        This is the inbound half: the far side started the exchange. Replying
        to the resulting message routes the answer back through *connector_name*
        (see :meth:`_route_reply`).

        Usually reached through the ``inbox`` granted to a connector that
        declares ``HookAnswer``, rather than called directly.

        Args:
            connector_name: Name of the connector the message arrived through.
            text: The message, as the user should see it.
            correlation_id: The far side's id for this exchange.

        Returns:
            str: The new message's id.

        Raises:
            ValueError: If no connector is registered under that name.
        """
        if connector_name not in self.connectors:
            raise ValueError("Connector '%s' not found" % connector_name)
        return self.receive_message(text, origin=connector_name, correlation_id=correlation_id)

    def _backend_for(self, hook: Hook) -> Any:
        """Returns the backend, refusing when it cannot do what is being asked.

        Checking the declaration rather than assuming the method is there is
        what stops a capability the backend never had from failing silently —
        the shape of bug that left ``/test`` reporting ✗ for months.

        Args:
            hook: The capability the caller needs.

        Returns:
            Any: The configured backend.

        Raises:
            RuntimeError: If there is no backend, or it does not declare *hook*.
        """
        if self.backend is None:
            raise RuntimeError("No backend configured")
        if not declares(self.backend, hook):
            raise RuntimeError(
                "Backend %r does not declare %s" % (name_of(self.backend), hook)
            )
        return self.backend

    @staticmethod
    def _start(obj: Any) -> None:
        """Calls ``initialize()`` when the object has one.

        Lifecycle is not a hook: an object holding nothing needs neither half,
        and making it declare that it holds nothing is ceremony.
        """
        if callable(getattr(obj, "initialize", None)):
            obj.initialize()

    def _inbox_for(self, connector_name: str) -> Inbox:
        """Builds the callable handed to a bidirectional connector."""
        def inbox(text: str, correlation_id: Optional[str] = None) -> str:
            return self.deliver(connector_name, text, correlation_id)
        return inbox

    def _route_reply(self, msg: ChatMessage) -> None:
        """Sends *msg* back through the connector it is answering, if any.

        A reply to a message that arrived through a connector is an answer owed
        to whoever asked. A connector failing here must not lose the message —
        it is already in the history — so the error is logged, not raised.
        """
        if msg.reply_to is None:
            return
        target = self._store.find(msg.reply_to)
        if target is None or target.origin is None:
            return

        connector = self.connectors.get(target.origin)
        if connector is None or not declares(connector, HookAnswer):
            logger.warning(
                "Cannot answer %s: connector %r is gone or does not declare %s",
                target.id, target.origin, HookAnswer,
            )
            return
        try:
            connector.answer(target.correlation_id, msg.text)
        except Exception as exc:
            logger.error("Connector %r failed to deliver the answer: %s", target.origin, exc)

    def close(self) -> None:
        """Shuts every connector down.

        A connector that owns a server or a thread needs to be told to stop;
        one that failed must not stop the others from being closed.
        """
        closeable = list(self.connectors.values()) + list(self.commands.values())
        if self.backend is not None:
            closeable.append(self.backend)
        for obj in closeable:
            shutdown = getattr(obj, "shutdown", None)
            if not callable(shutdown):
                continue
            try:
                shutdown()
            except Exception as exc:
                logger.error("%r failed to shut down: %s", name_of(obj), exc)

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
        cmd = self.commands[command_name]
        if not declares(cmd, HookExecute):
            raise RuntimeError(
                "Command %r does not declare %s" % (command_name, HookExecute)
            )

        try:
            result = cmd.execute(*args, **kwargs)
        except Exception as exc:
            logger.error("Error executing command '%s': %s", command_name, exc)
            # Both paths carry the same keys, so a handler declaring
            # (command, result, error) is called on failure too.
            self._hooks.trigger(HookCommandExecuted, command=command_name, result=None, error=exc)
            raise
        self._hooks.trigger(HookCommandExecuted, command=command_name, result=result, error=None)
        return result

    # === Connectors =================================================================

    def add_connector(self, connector: Any) -> None:
        """Registers *connector*, initializes it and registers its hooks.

        Args:
            connector: The connector to add.
        """
        name = name_of(connector)
        previous = self.connectors.get(name)
        if previous is not None:
            # Drop the replaced connector's hooks, otherwise it keeps being called
            # (and re-adding the same object would register it twice).
            logger.info("Replacing connector %r", name)
            self._hooks.unregister(previous)

        self.connectors[name] = connector
        self._hooks.register(connector)
        self._grant(connector, name)
        self._start(connector)
        self._hooks.trigger(HookConnectorAdded, connector=connector)

    def _grant(self, connector: Any, name: str) -> None:
        """Sets the attributes an object's declared hooks ask for.

        ``HookAnswer`` grants ``inbox`` and ``HookSay`` grants ``say``: both are
        ways into the chat that the object receives rather than imports, so the
        dependency keeps pointing inwards.
        """
        grants = {
            "inbox": lambda: self._inbox_for(name),
            "say"  : lambda: self.receive_message,
        }
        for hook in hooks_of(connector):
            for granted in hook.grants:
                build = grants.get(granted)
                if build is None:
                    logger.warning("Hook %s asks for unknown grant %r", hook, granted)
                    continue
                setattr(connector, granted, build())

    def add_command(self, cmd: Any) -> None:
        """Registers *cmd* under its declared name and grants what it asks for.

        Args:
            cmd: The command to add.

        Raises:
            TypeError: If *cmd* does not declare HookExecute. A command that
                cannot execute is not a command, and registering it silently
                would only surface as a missing ``/name`` much later.
        """
        if not declares(cmd, HookExecute):
            raise TypeError(
                "%r does not declare %s: a command must @require(HookExecute)"
                % (cmd, HookExecute)
            )
        name = name_of(cmd)
        previous = self.commands.get(name)
        if previous is not None:
            logger.info("Replacing command %r", name)
            self._hooks.unregister(previous)

        self.commands[name] = cmd
        self._hooks.register(cmd)
        self._grant(cmd, name)
        self._start(cmd)

    def ask_connector(self, connector_name: str, message: str, **kwargs) -> Any:
        """Asks a specific connector and returns its answer.

        Args:
            connector_name: Name of a registered connector.
            message: The message to send.
            **kwargs: Forwarded to the connector's ``ask``.

        Returns:
            Any: The connector's answer.

        Raises:
            ValueError: If no connector is registered under that name.
        """
        if connector_name not in self.connectors:
            raise ValueError("Connector '%s' not found" % connector_name)
        return self.connectors[connector_name].ask(message, **kwargs)

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
        saved = self._backend_for(HookSave).save(key, data)
        self._hooks.trigger(HookBackendSave, key=key, data=data)
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
        data = self._backend_for(HookLoad).load(key)
        self._hooks.trigger(HookBackendLoad, key=key, data=data)
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
        return self._backend_for(HookDelete).delete(key)

    # === Internals ==================================================================

    @staticmethod
    def _notify(observer: Optional[Callable[[Any], None]], payload: Any) -> None:
        """Calls *observer* if an owner attached one."""
        if observer is not None:
            observer(payload)
