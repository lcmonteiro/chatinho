"""The chat core: messages, commands, connectors and persistence.

:class:`ChatSession` holds every use case the chat offers and imports no UI
framework, so it can be driven from a TUI, a script or a test without a
terminal.

The conversation itself is **protected**: ``_send_message``, ``_send_command``
and ``_load_messages`` are not called directly by anyone. A plugin — a
connector, a command, or the presentation — declares the hook it needs, and
:meth:`attach` hands the capability over at registration. Declaring is the only
door in; implementing ``on_receive_message`` or ``on_receive_command`` is the
only door out.

What is left public is the other half of the job: registering plugins and
shutting them down.

``title``, ``welcome_message`` and anything about rendering live in the
presentation layer, not here.
"""

import logging
from datetime import datetime
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
    HookReceiveCommand,
    HookReceiveMessage,
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

    The five interfaces onto the conversation are reached only by declaring a
    hook — three the session grants, two it calls:

    - ``HookSendMessage``    grants ``send_message(text, reply_to=None)``.
    - ``HookSendCommand``    grants ``send_command(command)``.
    - ``HookLoadMessages``   grants ``load_messages(since=, start=, limit=)``.
    - ``HookReceiveMessage`` demands ``on_receive_message(msg)``.
    - ``HookReceiveCommand`` demands ``on_receive_command(msg)``.
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

        for connector in connectors or []:
            self.add_connector(connector)
        for cmd in commands or []:
            self.add_command(cmd)
        if self.backend is not None:
            self.attach(self.backend)

        logger.info(
            "Chat session initialized with %d connector(s), %d command(s) and %s backend",
            len(self.connectors), len(self.commands), type(backend).__name__,
        )

    # === Messages ===================================================================

    def _load_messages(
        self,
        *,
        since : Optional[datetime] = None,
        start : Optional[int] = None,
        limit : Optional[int] = None,
    ) -> List[ChatMessage]:
        """Reads the history, by time or by index. Granted by ``HookLoadMessages``.

        The three narrow independently and are applied in order, so
        ``load_messages(since=t, limit=20)`` is the last twenty since *t*.
        Called with nothing, it returns the whole history.

        Args:
            since: Keep only messages stamped at or after this moment.
            start: Index into what is left; drops everything before it.
            limit: Keep at most this many, counting back from the newest.

        Returns:
            List[ChatMessage]: A new list, oldest first.
        """
        msgs = self._store.messages
        if since is not None:
            msgs = [m for m in msgs if m.timestamp >= since]
        if start is not None:
            msgs = msgs[start:]
        if limit is not None:
            msgs = msgs[-limit:] if limit > 0 else []
        return msgs

    def _send_message(self, text: str, *, reply_to: Optional[str] = None) -> str:
        """Sends a normal message. Granted by ``HookSendMessage``.

        Replying to a message that arrived through a connector routes the
        answer back out before anyone is told about it, so a plugin reacting to
        ``on_receive_message`` sees a conversation already settled.

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
        self._route_reply(msg)
        self._hooks.trigger(HookReceiveMessage, msg=msg)
        self._hooks.trigger(HookMessageSent, msg=msg)
        return msg.id

    def _send_command(self, command: str) -> str:
        """Sends a command. Granted by ``HookSendCommand``.

        The command enters the history, everyone who declared
        ``HookReceiveCommand`` is told, and then the command registered under
        that name runs. Dispatch is the session's job, so a chat without a
        presentation still answers ``/help``.

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
        self._hooks.trigger(HookReceiveCommand, msg=msg)
        self.dispatch_command(command)
        self._hooks.trigger(HookMessageSent, msg=msg)
        return msg.id

    def _receive_message(
        self,
        text: str,
        *,
        reply_to       : Optional[str] = None,
        origin         : Optional[str] = None,
        correlation_id : Optional[str] = None,
    ) -> str:
        """Receives a message from outside. Granted by ``HookSay``.

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
        self._hooks.trigger(HookReceiveMessage, msg=msg)
        return msg.id

    def _deliver(
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
        return self._receive_message(text, origin=connector_name, correlation_id=correlation_id)

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
            return self._deliver(connector_name, text, correlation_id)
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
                self._receive_message("Command `%s%s` failed: %s" % (COMMAND_PREFIX, name, exc))
                return
            if result is not None:
                self._receive_message(str(result))
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

    def attach(self, obj: Any) -> None:
        """Registers *obj* for the hooks it declared and hands over its grants.

        The whole of the plugin contract, for anything that is not addressed by
        name: the presentation attaches this way, and so does the backend.
        Connectors and commands go through :meth:`add_connector` and
        :meth:`add_command`, which add the name and then call this.

        Args:
            obj: Anything declaring hooks.
        """
        self._hooks.register(obj)
        self._grant(obj, name_of(obj))
        self._start(obj)

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
        self.attach(connector)
        self._hooks.trigger(HookConnectorAdded, connector=connector)

    def _grant(self, connector: Any, name: str) -> None:
        """Sets the attributes an object's declared hooks ask for.

        ``HookAnswer`` grants ``inbox`` and ``HookSay`` grants ``say``: both are
        ways into the chat that the object receives rather than imports, so the
        dependency keeps pointing inwards.
        """
        grants = {
            "inbox"         : lambda: self._inbox_for(name),
            "say"           : lambda: self._receive_message,
            "send_message"  : lambda: self._send_message,
            "send_command"  : lambda: self._send_command,
            "load_messages" : lambda: self._load_messages,
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
        self.attach(cmd)

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

