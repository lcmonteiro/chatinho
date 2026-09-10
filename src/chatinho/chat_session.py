"""The chat core: peers, messages and the three verbs.

:class:`ChatSession` holds every use case the chat offers and imports no UI
framework, so it can be driven from a TUI, a script or a test without a
terminal.

Everyone in a chat is a **peer** with an integer id. :data:`LOCAL` —
zero — is the user; every connector and every tool is numbered from one. A
peer is a plain class that declares what it can do, and the session
hands the capabilities over at :meth:`add_connector`.

The conversation is protected: ``_say``, ``_ask``, ``_answer`` and
``_load_messages`` are never called directly. Declaring a hook is the only door
in, and implementing ``listen`` or ``answer`` is the only door out.

Every peer has its own queue and its own task draining it, so a
subsystem that takes a second to answer holds up nobody but itself.
"""

import asyncio
import logging
from datetime import datetime
from inspect import isawaitable
from typing import Any, Dict, List, Optional

from .chat_hooks import (
    HookExecute,
    HookForget,
    HookLoad,
    HookAnswer,
    HookListen,
    declares,
    hooks_of,
    declared_id,
    name_of,
)
from .chat_message import TOOL, ChatMessage, MessageStore

logger = logging.getLogger(__name__)

COMMAND_PREFIX : str = "/"


class ChatSession:
    """Routes messages between peers, and keeps the history.

    The five interfaces onto the conversation are reached only by declaring a
    hook — three the session grants, two it calls:

    - ``HookSay``      grants  ``say(text, reply_to=None)``.
    - ``HookAsk``      grants  ``ask(to, text)``, which awaits the answer.
    - ``HookContext``  grants  ``context(since=, start=, limit=)``.
    - ``HookListen``   demands ``listen(msg)`` — every message that crosses.
    - ``HookAnswer``   demands ``answer(msg)`` — someone asked you.
    """

    def __init__(
        self,
        connectors : Optional[List[Any]] = None,
        commands   : Optional[List[Any]] = None,
        backend    : Optional[Any] = None,
        recall     : int = 200,
    ) -> None:
        #: Where the conversation goes when it is no longer recent.
        self.backend : Optional[Any] = backend
        #: How much of the archive ``start()`` pulls back into the session.
        self.recall  : int = recall

        self._store    : MessageStore = MessageStore()
        self._connectors    : Dict[int, Any] = {}
        self._queues   : Dict[int, "asyncio.Queue[ChatMessage]"] = {}
        self._tasks    : Dict[int, asyncio.Task] = {}
        self._pending  : Dict[str, "asyncio.Future[str]"] = {}
        self._next_id  : int = 1
        self._started  : bool = False
        self._closed   : bool = False
        #: ids of peers/commands whose initialize() has already run.
        self._initialized : set = set()

        #: Commands are not peers: no id, no queue, nothing addressed to them.
        #: They run when someone runs them, and answer whoever did.
        self.commands : Dict[str, Any] = {}

        for who in connectors or []:
            self.add_connector(who)
        for cmd in commands or []:
            self.add_command(cmd)
        if backend is not None:
            # A peer like any other: it gets an id and a queue, and it
            # hears the conversation rather than being pushed at. `backend` is
            # only sugar for the role — the session finds what it needs by what
            # the thing declared, not by which parameter it arrived in.
            self.add_connector(backend)

    # === Peers ===============================================================

    def add_connector(self, connector: Any, at: Optional[int] = None) -> int:
        """
        Registers *connector*, hands over its grants and returns its id.

        The whole plugin contract. The id comes from the first of three: what
        the caller pins here, what the class declared with
        ``@connector(name, id=…)``, or the next free number. The terminal
        declares ``id=LOCAL`` rather than being attached specially, because
        being peer zero is what it *is*, not a favour the caller does it.

        Args:
            connector: Anything declaring hooks.
            at: The id to register it under; the declared one, or the next
                free number, when omitted.

        Returns:
            int: The id the peer now answers to.

        Raises:
            ValueError: If the id is already taken.
        """
        if at is None:
            at = declared_id(connector)
        if at is None:
            at = self._next_id
            self._next_id += 1
        elif at in self._connectors:
            raise ValueError("Id %d is already taken by %r" % (at, name_of(self._connectors[at])))

        # peer_id, not id: Textual's DOMNode already owns `id` and validates it
        # as a string. A peer rarely needs its own number anyway — the
        # grants bind `frm` for it — but knowing it costs nothing.
        connector.peer_id = at
        self._connectors[at] = connector
        self._queues[at] = asyncio.Queue()
        self._grant(connector, at)
        return at

    def add_command(self, cmd: Any) -> str:
        """Registers a command under its declared name and returns it.

        A command is not a peer. It has no id and no queue, nothing is
        addressed to it, and it hears nothing — it runs when someone runs it.
        What it may do to the conversation is whatever it declared: nothing at
        all, or ``HookSay`` to write while it works.

        Args:
            cmd: A class declaring :data:`HookExecute`.

        Returns:
            str: The name it answers to.

        Raises:
            TypeError: If *cmd* does not declare HookExecute. A command that
                cannot execute is not a command, and registering it silently
                would only surface as a missing ``/name`` much later.
        """
        if not declares(cmd, HookExecute):
            raise TypeError(
                "%r does not declare %s: a command must @require(HookExecute)"
                % (cmd, HookExecute))
        name = name_of(cmd)
        self.commands[name] = cmd
        # TOOL, not LOCAL: what a command writes is not the user speaking.
        self._grant(cmd, TOOL)
        return name

    def _invoke_for(self, frm: int):
        """Builds the ``invoke`` granted to a peer, bound to that peer.

        A command is not a peer, so it has no id: the invocation is addressed
        to ``TOOL`` and what the command answered comes back from ``TOOL``,
        replying to it. Both cross the session like anything else, so a listener
        sees the whole of what happened — but the invocation is *addressed*, not
        a broadcast, so a peer that answers what the room says does not answer
        somebody else's ``/help``.
        """
        async def invoke(name: str, args: str = "") -> Optional[str]:
            cmd = self.commands.get(name)
            if cmd is None:
                logger.info("No command named %r", name)
                return None
            asked = ChatMessage(
                id=self._store.new_id(),
                text="/%s %s" % (name, args) if args else "/%s" % name,
                frm=frm, to=TOOL,
            )
            await self._post(asked)
            try:
                reply = await cmd.execute(args, by=frm)
            except Exception:
                logger.error("Command %r failed", name, exc_info=True)
                raise
            if reply is not None:
                await self._post(ChatMessage(
                    id=self._store.new_id(), text=reply, frm=TOOL, to=None, reply_to=asked.id,
                ))
            return reply
        return invoke

    def id_of(self, name: str) -> Optional[int]:
        """
        Returns the id of the peer with that visible name, or None.

        The name is what the chat displays and what the user types after ``/``;
        the id is what messages are addressed to. Keeping them apart is what
        lets a peer be renamed without breaking replies in flight.
        """
        for at, who in self._connectors.items():
            if name_of(who) == name:
                return at
        return None

    def _peers(self) -> Dict[int, Any]:
        """Everyone registered, by id. Granted by ``HookPeers``."""
        return dict(self._connectors)

    def _commands(self) -> Dict[str, Any]:
        """Every command registered, by name. Granted by ``HookCommands``."""
        return dict(self.commands)

    def _grant(self, who: Any, at: int) -> None:
        """Sets the attributes *who*'s declared hooks ask for.

        Each grant is bound to the peer's own id, so nobody can speak in
        another's name: the ``frm`` of a message is not an argument.
        """
        grants = dict(
            say     = lambda: self._say_for(at),
            ask     = lambda: self._ask_for(at),
            context = lambda: self._context,
            invoke  = lambda: self._invoke_for(at),
            peers   = lambda: self._peers,
            commands= lambda: self._commands,
        )
        for hook in hooks_of(who):
            for granted in hook.grants:
                build = grants.get(granted)
                if build is None:
                    logger.warning("Hook %s asks for unknown grant %r", hook, granted)
                    continue
                setattr(who, granted, build())

    async def _initialize(self, obj: Any) -> None:
        """
        Calls ``initialize()`` when the object has one, from :meth:`start`.

        ``start`` has a running loop, unlike ``add_connector``/``add_command``,
        so ``initialize`` may be a coroutine function: it is awaited when it
        returns one, and simply called when it does not.
        """
        init = getattr(obj, "initialize", None)
        if not callable(init):
            return
        result = init()
        if isawaitable(result):
            await result

    # === The three verbs, bound to one speaker ======================================

    def _say_for(self, frm: int):
        async def say(text: str, *, reply_to: Optional[str] = None) -> str:
            return await self._post(ChatMessage(
                id=self._store.new_id(), text=text, frm=frm, to=None, reply_to=reply_to,
            ))
        return say

    def _ask_for(self, frm: int):
        async def ask(to: int, text: str) -> str:
            if to not in self._connectors:
                raise ValueError("No peer with id %d" % to)
            msg = ChatMessage(id=self._store.new_id(), text=text, frm=frm, to=to)
            future : "asyncio.Future[str]" = asyncio.get_running_loop().create_future()
            self._pending[msg.id] = future
            await self._post(msg)
            return await future
        return ask

    async def _post(self, msg: ChatMessage) -> str:
        """
        Keeps *msg* and puts it in the queue of everyone it is for.

        An answer to an ask that is still waiting resolves that wait, and is
        not delivered to the asker a second time — it is already holding it.
        Everyone who listens still hears it: there is one conversation, and the
        replies are part of it.
        """
        self._store.add(msg)
        waiting  = self._pending.pop(msg.reply_to, None) if msg.reply_to else None
        resolved = waiting is not None and not waiting.done()
        if resolved:
            waiting.set_result(msg.text)          # type: ignore[union-attr]

        # You never hear yourself; that is the whole of the loop protection.
        listeners = {at for at, who in self._connectors.items()
                     if at != msg.frm and declares(who, HookListen)}
        audience  = {msg.to} if msg.to is not None and not resolved else set()
        for at in listeners | audience:
            queue = self._queues.get(at)
            if queue is not None:
                queue.put_nowait(msg)
        return msg.id

    async def _deliver(self, who: Any, msg: ChatMessage) -> None:
        """
        Hands one message to one peer, every way it declared to get it.

        The two are not exclusive: something that listens *and* answers gets
        both calls for the same message, because it asked for both.

        What ``answer`` returns is posted in the peer's name. Returning None is
        not a failure: the ask stays waiting, and whatever the peer says later
        with ``reply_to`` set resolves it.
        """
        if declares(who, HookListen):
            await who.listen(msg)

        if msg.is_broadcast:
            return
        at = getattr(who, "peer_id", None)
        if at is None or msg.to != at:
            return
        if not declares(who, HookAnswer):
            logger.warning("%r was asked but does not declare %s", name_of(who), HookAnswer)
            return
        reply = await who.answer(msg)
        if reply is not None:
            await self._post(ChatMessage(
                id=self._store.new_id(), text=reply, frm=at, to=msg.frm, reply_to=msg.id,
            ))

    async def _drain(self, at: int) -> None:
        """
        One peer's queue, one message at a time.

        A peer that raises is logged and its queue carries on: one bad
        subsystem must not take the chat down, nor stall its own backlog.
        """
        queue = self._queues[at]
        while True:
            msg = await queue.get()
            try:
                await self._deliver(self._connectors[at], msg)
            except Exception:
                logger.error("Peer %d failed on %s", at, msg.id, exc_info=True)
            finally:
                queue.task_done()

    # === History ====================================================================

    def _context(
        self,
        *,
        since : Optional[datetime] = None,
        start : Optional[int] = None,
        limit : Optional[int] = None,
    ) -> List[ChatMessage]:
        """
        The conversation so far, by time or by index. Granted by ``HookContext``.

        One interface over two tiers: what was said this session, and what
        :meth:`start` recalled from the archive. Whoever asks never learns
        which tier a message came from.

        Deliberately synchronous, and that costs something worth naming: the
        window is whatever ``recall`` pulled back at startup, so asking for
        older than that returns nothing rather than reaching down again. Making
        it reach would make it a coroutine, and the terminal renders the log
        from inside a synchronous Textual paint.

        The three narrow independently and are applied in order, so
        ``load_messages(since=t, limit=20)`` is the last twenty since *t*.

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

    # === Lifecycle ==================================================================

    def run(self) -> None:
        """
        Runs the whole chat, and returns when it is over.

        The entry point for a program whose job *is* the chat: it owns the
        event loop, so there must not be one running already. From inside a
        loop, drive :meth:`start` and :meth:`close` yourself.

        A peer that runs until it is finished — a terminal, a server, a stdin
        reader — writes ``serve()``, and the session runs those and closes when
        the first of them returns. A session with none of them runs until it is
        interrupted, which is what a bot wants.

        Raises:
            RuntimeError: There is already an event loop on this thread.
        """
        try:
            asyncio.run(self._serve())
        except KeyboardInterrupt:
            pass

    async def _serve(self) -> None:
        """Starts everything, waits for it to be over, and closes."""
        await self.start()
        serving = {
            asyncio.create_task(who.serve(), name=name_of(who))
            for who in self._connectors.values()
            if callable(getattr(who, "serve", None))
        }
        try:
            if serving:
                # The first to finish ends the chat: quitting the terminal is
                # the end of it, even when a server is still listening.
                done, pending = await asyncio.wait(serving, return_when=asyncio.FIRST_COMPLETED)
                for task in pending:
                    task.cancel()
                for task in done:
                    task.result()            # let a peer's failure be seen
            else:
                await asyncio.Event().wait()  # nothing serves: until interrupted
        finally:
            # Closes on the way out however that happens — a peer finishing, a
            # peer raising, or this being cancelled. Cancellation is not
            # swallowed: whoever cancelled is owed the CancelledError, and
            # ``run`` turns the Ctrl-C case into a quiet exit itself.
            await self.close()

    async def start(self) -> None:
        """
        Initializes every peer and command, then starts one drain task per peer.

        Separate from construction because both need a running loop, and a
        session is usually built before there is one — ``initialize()`` runs
        here rather than at ``add_connector``/``add_command`` for the same
        reason, which is also why it may now be a coroutine function.
        Initializing runs before the archive is recalled, since a backend's own
        ``initialize()`` is usually what makes it able to ``load()`` at all.

        Calling it twice is a no-op *for the archive*: :meth:`run` starts the
        session, and a presentation that also starts it when it mounts must not
        load the older context on top of itself. Initializing and the drain
        tasks are another matter — calling it again picks up whatever was
        attached since, which is how a peer added after the session started
        ever runs, or is initialized, at all.
        """
        for who in list(self._connectors.values()) + list(self.commands.values()):
            if id(who) not in self._initialized:
                self._initialized.add(id(who))
                await self._initialize(who)
        if not self._started:
            self._started = True
            await self._recall()
        for at in self._queues:
            if at not in self._tasks or self._tasks[at].done():
                self._tasks[at] = asyncio.create_task(self._drain(at))

    async def close(self) -> None:
        """
        Stops the drain tasks and shuts every peer down.

        A peer holding a server or a thread would otherwise outlive the
        chat it was serving. Calling it twice is a no-op, for the same reason
        :meth:`start` is.
        """
        if self._closed:
            return
        self._closed = True
        # Drain before cancelling: a message still in a queue is a message a
        # listener has not held yet, and cancelling first made "the
        # conversation survives" true only sometimes.
        try:
            await asyncio.wait_for(
                asyncio.gather(*(q.join() for q in self._queues.values())),
                timeout=5.0,
            )
        except asyncio.TimeoutError:
            logger.warning("Gave up waiting for the queues to drain")
        for task in self._tasks.values():
            task.cancel()
        self._tasks.clear()
        for who in list(self._connectors.values()) + list(self.commands.values()):
            shutdown = getattr(who, "shutdown", None)
            if callable(shutdown):
                try:
                    shutdown()
                except Exception:
                    logger.error("Shutting %r down failed", name_of(who), exc_info=True)

    # === The older tier =============================================================

    async def _recall(self) -> None:
        """
        Pulls the tail of the archive back into the session.

        Called once by :meth:`start`, before anyone can ask for context, so a
        chat reopens where it left off. A backend that cannot recall is not an
        error: it simply has nothing to give back.
        """
        holder = next((w for w in self._connectors.values() if declares(w, HookLoad)), None)
        if holder is None:
            return
        try:
            for msg in await holder.load(limit=self.recall):
                self._store.add(msg)
        except Exception:
            logger.error("Loading the older context failed; starting empty", exc_info=True)

    async def forget(self, before: Optional[datetime] = None) -> int:
        """
        Drops archived messages older than *before*, or all of them.

        Args:
            before: Keep everything from this moment on; None forgets the lot.

        Returns:
            int: How many the backend dropped, or zero when it cannot forget.
        """
        holder = next((w for w in self._connectors.values() if declares(w, HookForget)), None)
        if holder is None:
            return 0
        return await holder.forget(before=before)
