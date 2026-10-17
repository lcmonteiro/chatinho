"""The chat core: peers, messages and the three verbs.

:class:`ChatSession` holds every use case the chat offers and imports no UI
framework, so it can be driven from a TUI, a script or a test without a
terminal.

Everyone in a chat is a **peer** with an integer id. :data:`LOCAL` —
zero — is the user; every other peer is numbered from one. A command is not
a peer and has no id. A peer is a plain class that declares what it can do,
and the session hands the capabilities over at :meth:`add_connector`.

The conversation is protected: no peer calls the session's own methods.
Declaring a hook is the only door in, and implementing ``listen`` or
``answer`` is the only door out.

Every delivery of a message to a peer is its own task, so a subsystem that
takes a second to answer holds up nobody, not even its own next question, and
a peer may ask a peer that is already asking it. Peers keep no state of the
conversation: it lives here, and in the backend.
"""

import asyncio
import logging
from contextvars import ContextVar
from datetime import datetime
from inspect import isawaitable
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from .hooks import HookAnswer, HookExecute, HookForget, HookKeep, HookLink, HookListen, HookLoad
from .hooks import declared_id, declares, hooks_of, name_of
from .message import LOCAL, TOOL
from .message import Attachment, ChatMessage, MessageID, MessageStore, Reply, ReplyStatus, Secret
from .query import Query

#: How deeply the question being answered in this task is nested; 0 when none is.
#: Set by the session around ``answer``, read when that answer asks again.
_ANSWERING : ContextVar[int] = ContextVar("chatinho_answering", default=0)

logger = logging.getLogger(__name__)

COMMAND_PREFIX : str = "/"


def _checked(reply: Any, what: str) -> Optional[Reply]:
    """*reply* itself if it is a Reply or None; anything else, a bare string most often, raises TypeError."""
    if reply is not None and not isinstance(reply, Reply):
        raise TypeError("%s returned %s; it must return a Reply or None" % (what, type(reply).__name__))
    return reply


class ChatSession:
    """Routes messages between peers, and keeps the history.

    The conversation is reached only by declaring a hook. The five most used
    are below; ``docs/SPEC.md`` has all fourteen:

    - ``HookSay``      grants  ``say(text, *, to=None, reply_to=None, attachments=())``.
    - ``HookAsk``      grants  ``ask(to, text, *, attachments=())``, which awaits the answer.
    - ``HookContext``  grants  ``context(since=, start=, limit=)``.
    - ``HookListen``   demands ``listen(msg)`` — every message that crosses.
    - ``HookAnswer``   demands ``answer(msg)`` — someone asked you.

    Four roles arrive as four parameters, and every one of them is a plain
    class the session tells apart by what it declared, never by which parameter
    carried it: ``frontend`` speaks for the person, ``connectors`` are who they
    are talking to, ``commands`` only run, and ``backend`` listens and recalls.
    """

    #: How long :meth:`close` waits for the deliveries in flight, in seconds.
    CLOSE_TIMEOUT : float = 5.0

    def __init__(
        self,
        connectors : Optional[List[Any]] = None,
        commands   : Optional[List[Any]] = None,
        frontend   : Optional[Any] = None,
        backend    : Optional[Any] = None,
        recall     : int = 200,
        max_depth  : int = 8,
    ) -> None:
        #: Who speaks for the person: a terminal, a stdin reader, an inbox.
        self.frontend : Optional[Any] = frontend
        #: Where the conversation goes when it is no longer recent.
        self.backend  : Optional[Any] = backend
        #: How much of the archive ``start()`` pulls back into the session.
        self.recall   : int = recall
        #: How deeply asks may nest; a deeper question is answered with an error.
        self.max_depth : int = max_depth

        #: The conversation, in the order it was posted: the one source of its order.
        self._store       : MessageStore = MessageStore()
        #: Every peer, by id; the frontend is at LOCAL.
        self._connectors  : Dict[int, Any] = {}
        #: Asks still waiting for their answer, by the id of the question.
        self._pending     : Dict[MessageID, "asyncio.Future[ChatMessage]"] = {}
        #: Peers that start() has started; deliveries to the others are held.
        self._running     : Set[int] = set()
        #: Deliveries waiting for their peer to start, in the order they were posted.
        self._held        : List[Tuple[int, ChatMessage, bool]] = []
        #: Deliveries in flight, one task each; close() waits for them.
        self._deliveries  : Set["asyncio.Task[None]"] = set()
        #: How deeply each question still being delivered is nested.
        self._depth       : Dict[MessageID, int] = {}
        #: The id the next peer without a declared or pinned one gets.
        self._next_id     : int = 1
        #: Whether start() has recalled the archive; it does so only once.
        self._started     : bool = False
        #: Whether close() is waiting for the deliveries in flight.
        self._closing     : bool = False
        #: Whether close() has finished waiting; nothing is delivered after it.
        self._closed      : bool = False
        #: ids of peers/commands whose initialize() has already run.
        self._initialized : set = set()

        #: Commands are not peers: no id, nothing addressed to them.
        #: They run when someone runs them, and answer whoever did.
        self.commands : Dict[str, Any] = {}

        if frontend is not None:
            # Pinned rather than merely registered, and that is the one place
            # `frontend` and `backend` differ: a backend has no id of its own,
            # while a frontend *is* an id. Passing something that never
            # declared `@frontend` would otherwise land it at one, leaving the
            # chat with nobody at zero and nothing saying so.
            self.add_connector(frontend, at=LOCAL)
        for who in connectors or []:
            self.add_connector(who)
        for cmd in commands or []:
            self.add_command(cmd)
        if backend is not None:
            # A peer like any other: it gets an id, and it
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
        ``@connector(name, id=…)`` or ``@frontend(name)``, or the next free
        number. A presentation declares its way to :data:`LOCAL` rather than
        being attached specially, because being peer zero is what it *is*, not
        a favour the caller does it.

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
            # Past any id already taken: a peer pinned at one was otherwise
            # silently replaced by the next one numbered.
            while self._next_id in self._connectors:
                self._next_id += 1
            at = self._next_id
            self._next_id += 1
        elif at in self._connectors:
            raise ValueError("Id %d is already taken by %r" % (at, name_of(self._connectors[at])))

        # peer_id, not id: Textual's DOMNode already owns `id` and validates it
        # as a string. A peer rarely needs its own number anyway — the
        # grants bind `frm` for it — but knowing it costs nothing.
        connector.peer_id = at
        self._connectors[at] = connector
        self._grant(connector, at)
        return at

    def add_command(self, cmd: Any) -> str:
        """Registers a command under its declared name and returns it.

        A command is not a peer. It has no id, nothing is
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
            if _checked(reply, "Command %r's execute" % name) is None:
                return None
            result = ChatMessage(
                id=self._store.new_id(), text=reply.text, frm=TOOL, to=None, reply_to=asked.id,
            )
            await self._kept(result, reply.attachments)
            await self._post(result)
            return reply.text
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

    def _first(self, hook: Any) -> Optional[Any]:
        """The first peer that declares *hook*, or None: the backend, for the hooks only it has."""
        return next((who for who in self._connectors.values() if declares(who, hook)), None)

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
            context = lambda: self._context_for(at),
            invoke  = lambda: self._invoke_for(at),
            peers   = lambda: self._peers,
            commands= lambda: self._commands,
            locate  = lambda: self.locate,
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
        async def say(
            text        : str,
            *,
            to          : Optional[int] = None,
            reply_to    : Optional[MessageID] = None,
            attachments : Sequence[Attachment] = (),
            credentials : Optional[Dict[str, Secret]] = None,
        ) -> MessageID:
            if to is not None and (to not in self._connectors or to == frm):
                raise ValueError("No other peer with id %d" % to)
            msg = ChatMessage(id=self._store.new_id(), text=text, frm=frm, to=to, reply_to=reply_to)
            if credentials is not None:
                msg.credentials = credentials     # the lender's own mapping, so it can clear it
            # The speaker's `to` is never changed: who the session asks goes
            # beside it, so a say routed to a peer is still said to the room.
            if to is not None:
                msg.asked_of = to
            elif frm != TOOL:
                msg.asked_of = self._answerer_of(frm, reply_to)
            await self._kept(msg, attachments)
            return await self._post(msg)
        return say

    def _answerer_of(self, frm: int, reply_to: Optional[MessageID]) -> Optional[int]:
        """The peer a say with no ``to`` is asked of, or None for a broadcast.

        A reply goes back to whoever said what it replies to; any other say,
        to the only peer that answers. Either way the speaker and the frontend
        do not count — the frontend speaks for the person, and a say must not
        turn into a question put to them — and a peer that does not answer
        cannot be asked. A reply to something no longer in the session, or
        said by a command, is a broadcast.
        """
        def answers(at: int) -> bool:
            return at not in (frm, LOCAL) and declares(self._connectors[at], HookAnswer)

        if reply_to is not None:
            parent = self._store.find(reply_to)
            author = parent.frm if parent is not None else None
            return author if author in self._connectors and answers(author) else None
        answering = [at for at in self._connectors if answers(at)]
        return answering[0] if len(answering) == 1 else None

    def _ask_for(self, frm: int):
        async def ask(
            to          : int,
            text        : str,
            *,
            attachments : Sequence[Attachment] = (),
        ) -> Reply:
            if to not in self._connectors:
                raise ValueError("No peer with id %d" % to)
            msg = ChatMessage(id=self._store.new_id(), text=text, frm=frm, to=to, asked_of=to)
            await self._kept(msg, attachments)
            future : "asyncio.Future[ChatMessage]" = asyncio.get_running_loop().create_future()
            self._pending[msg.id] = future
            try:
                await self._post(msg)
                answered = await future
            finally:
                self._pending.pop(msg.id, None)
            # The status says whether it answered, asked back or failed; what
            # the answer attached is with the backend, under its id.
            return Reply(answered.text, status=answered.status)
        return ask

    async def _kept(self, msg: ChatMessage, attachments: Sequence[Attachment]) -> None:
        """Hands what *msg* carries to the backend, before *msg* is posted.

        The message itself stays text. With no backend declaring ``HookKeep``
        the attachments have nowhere to go and are dropped; one that raises is
        logged, and the message is posted all the same — a broken store must
        not silence the chat.

        Args:
            msg: The message the attachments belong to; its id is the key.
            attachments: What was attached; nothing happens when empty.
        """
        if not attachments:
            return
        keeper = self._first(HookKeep)
        if keeper is None:
            logger.debug("No backend keeps attachments; dropping %d of %s", len(attachments), msg.id)
            return
        try:
            await keeper.keep(msg.id, tuple(attachments))
        except Exception:
            logger.error("Keeping the attachments of %s failed", msg.id, exc_info=True)

    async def _post(self, msg: ChatMessage) -> MessageID:
        """
        Keeps *msg* and starts delivering it to everyone it is for.

        Each delivery is its own task, so this returns before anyone has heard
        it. A question, anything asked of a peer, is given its depth: one more
        than the question being answered in this task, if any.

        Who is asked is ``asked_of``, set where the message was made, never its
        shape: the user following up on an answer and the answer to that
        follow-up look alike. An answer — what a peer's ``answer`` returned, or
        a reply the session posts in its name — is asked of nobody: it may
        resolve an ask that is waiting, and everyone who listens hears it.
        """
        self._store.add(msg)
        # Only the peer the question was asked of resolves its ask: anyone
        # else's reply is heard like any message, and the ask keeps waiting.
        question = self._store.find(msg.reply_to) if msg.reply_to else None
        waiting  = self._pending.get(msg.reply_to) if msg.reply_to else None
        resolved = (waiting is not None and not waiting.done()
                    and question is not None and question.asked_of == msg.frm)
        if resolved:
            del self._pending[msg.reply_to]       # type: ignore[arg-type]
            waiting.set_result(msg)               # type: ignore[union-attr]

        # You never hear yourself; that is the whole of the loop protection.
        listeners = {at for at, who in self._connectors.items()
                     if at != msg.frm and declares(who, HookListen)}
        audience  = {msg.asked_of} if msg.asked_of is not None and not resolved else set()
        audience &= self._connectors.keys()
        if audience:
            self._depth[msg.id] = _ANSWERING.get() + 1
        for at in sorted(listeners | audience):
            self._dispatch(at, msg, at in audience)
        return msg.id

    def _dispatch(self, at: int, msg: ChatMessage, asked: bool) -> None:
        """Delivers *msg* to peer *at* now, or once it has started; *asked* if it is put to *at*."""
        if self._closed:
            return
        if at in self._running:
            task = asyncio.create_task(self._delivery(at, msg, asked))
            self._deliveries.add(task)
            task.add_done_callback(self._deliveries.discard)
        else:
            self._held.append((at, msg, asked))

    async def _delivery(self, at: int, msg: ChatMessage, asked: bool) -> None:
        """
        One message, to one peer, on its own task.

        A peer that raises is logged and nothing else stops: one bad
        subsystem must not take the chat down.
        """
        try:
            await self._deliver(self._connectors[at], msg, asked)
        except Exception:
            logger.error("Peer %d failed on %s", at, msg.id, exc_info=True)
        finally:
            if asked:
                self._depth.pop(msg.id, None)

    async def _deliver(self, who: Any, msg: ChatMessage, asked: bool) -> None:
        """
        Hands one message to one peer, every way it declared to get it.

        The two are not exclusive: something that listens *and* answers gets
        both calls for the same message, because it asked for both. Only a
        message put to the peer (*asked*) is answered: a reply that resolved
        the peer's own ask is only heard, never answered again.

        What ``answer`` returns is posted in the peer's name. Returning None is
        not a failure: the ask stays waiting, and whatever the peer says later
        with ``reply_to`` set resolves it.
        """
        if declares(who, HookListen):
            _ANSWERING.set(0)              # hearing is not answering
            await who.listen(msg)

        if not asked:
            return
        at = getattr(who, "peer_id", None)
        if at is None:
            return
        if not declares(who, HookAnswer):
            logger.warning("%r was asked but does not declare %s", name_of(who), HookAnswer)
            return
        depth = self._depth.get(msg.id, 1)
        _ANSWERING.set(depth)
        if depth > self.max_depth:
            if msg.reply_to is not None:
                # A reply said back to whoever it replies to: nobody waits on
                # it, so it is dropped rather than answered with an error that
                # would be said back in turn.
                logger.warning("Dropped %s: nested deeper than %d", msg.id, self.max_depth)
                return
            await self._answered(at, msg, Reply("too many nested asks (limit %d)" % self.max_depth,
                                                status=ReplyStatus.ERROR))
            return
        try:
            reply = _checked(await who.answer(msg), "%s's answer" % name_of(who))
        except Exception as exc:
            # The asker is owed one reply, and a failure is one. An ask that is
            # waiting raises; a say that was asked of this peer gets an error
            # reply, so whoever waits on it hears. _delivery logs it either way.
            waiting = self._pending.pop(msg.id, None)
            if waiting is not None and not waiting.done():
                waiting.set_exception(exc)
            else:
                await self._post(ChatMessage(
                    id=self._store.new_id(), text="%s failed: %s" % (name_of(who), type(exc).__name__),
                    frm=at, to=msg.frm, reply_to=msg.id, status=ReplyStatus.ERROR))
            raise
        if reply is not None:
            await self._answered(at, msg, reply)

    async def _answered(self, at: int, msg: ChatMessage, reply: Reply) -> None:
        """Posts *reply* in the name of peer *at*, as its answer to *msg*."""
        answered = ChatMessage(id=self._store.new_id(), text=reply.text, frm=at, to=msg.frm,
                               reply_to=msg.id, status=reply.status)
        await self._kept(answered, reply.attachments)
        await self._post(answered)

    # === History ====================================================================

    def _context_for(self, at: int):
        """The ``context`` grant for the peer at *at*, so :data:`SELF` means it."""
        def context(
            query : Optional[Query] = None,
            *,
            since : Optional[datetime] = None,
            start : Optional[int] = None,
            limit : Optional[int] = None,
        ) -> List[ChatMessage]:
            return self._context(query, since=since, start=start, limit=limit, asker=at)
        return context

    def _context(
        self,
        query : Optional[Query] = None,
        *,
        since : Optional[datetime] = None,
        start : Optional[int] = None,
        limit : Optional[int] = None,
        asker : Optional[int] = None,
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

        A :class:`~chatinho.query.Query` narrows first; then the three
        keywords narrow independently and are applied in order, so
        ``context(since=t, limit=20)`` is the last twenty since *t*.

        Args:
            query: Which messages, as data; :data:`~chatinho.query.SELF` in it
                means *asker*.
            since: Keep only messages stamped at or after this moment.
            start: Index into what is left; drops everything before it.
            limit: Keep at most this many, counting back from the newest.
            asker: The id of the peer asking, which :data:`SELF` resolves to.

        Returns:
            List[ChatMessage]: A new list, oldest first.
        """
        msgs = self._store.messages
        if query is not None:
            msgs = query.select(msgs, asker)
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
                if pending:
                    await asyncio.wait(pending)   # let each finish being cancelled
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
        Initializes every peer and command, then starts delivering to them.

        Separate from construction because both need a running loop, and a
        session is usually built before there is one — ``initialize()`` runs
        here rather than at ``add_connector``/``add_command`` for the same
        reason, which is also why it may now be a coroutine function.
        Initializing runs before the archive is recalled, since a backend's own
        ``initialize()`` is usually what makes it able to ``load()`` at all.

        Calling it twice is a no-op *for the archive*: :meth:`run` starts the
        session, and a presentation that also starts it when it mounts must not
        load the older context on top of itself. Initializing and delivering
        are another matter — calling it again picks up whatever was attached
        since, which is how a peer added after the session started ever hears
        anything, or is initialized, at all. What was said to a peer before it
        started is delivered to it now, in the order it was said.
        """
        for who in list(self._connectors.values()) + list(self.commands.values()):
            if id(who) not in self._initialized:
                self._initialized.add(id(who))
                await self._initialize(who)
        if not self._started:
            self._started = True
            await self._recall()
        if self._closed:
            return
        self._running.update(self._connectors)
        held, self._held = self._held, []
        for at, msg, asked in held:
            self._dispatch(at, msg, asked)

    async def close(self) -> None:
        """
        Lets the deliveries in flight finish, then shuts every peer down.

        It waits up to :attr:`CLOSE_TIMEOUT` seconds, for what is in flight and
        for what that sets off, then warns and cancels the rest, and fails
        every ask still waiting, so nothing hangs on a chat that is gone.

        A peer holding a server or a thread would otherwise outlive the
        chat it was serving. Calling it twice is a no-op, for the same reason
        :meth:`start` is.
        """
        if self._closed or self._closing:
            return
        self._closing = True
        # Wait before cancelling: a delivery in flight is a message a listener
        # has not held yet, and cancelling first made "the conversation
        # survives" true only sometimes.
        loop     = asyncio.get_running_loop()
        deadline = loop.time() + self.CLOSE_TIMEOUT
        current  = asyncio.current_task()
        while True:
            busy = {t for t in self._deliveries if t is not current}
            if not busy:
                break
            left = deadline - loop.time()
            if left <= 0:
                logger.warning("Gave up waiting for %d deliveries to finish", len(busy))
                break
            await asyncio.wait(busy, timeout=left)
        self._closed = True
        self._held.clear()
        busy = {t for t in self._deliveries if t is not current}
        for task in busy:
            task.cancel()
        if busy:
            await asyncio.wait(busy, timeout=1.0)
        for future in list(self._pending.values()):
            if not future.done():
                future.set_exception(RuntimeError("the chat closed"))
        self._pending.clear()
        await self._shutdown()

    async def _shutdown(self) -> None:
        """Calls every ``shutdown()``, then awaits the ones that are coroutines.

        Synchronous ones run in order, as they always did. The asynchronous
        ones run together, within :attr:`CLOSE_TIMEOUT`: one that will not
        finish is cancelled with a warning, so it cannot hang the close.
        """
        pending : Dict["asyncio.Future[Any]", str] = {}
        for who in list(self._connectors.values()) + list(self.commands.values()):
            shutdown = getattr(who, "shutdown", None)
            if not callable(shutdown):
                continue
            try:
                result = shutdown()
            except Exception:
                logger.error("Shutting %r down failed", name_of(who), exc_info=True)
                continue
            if isawaitable(result):
                pending[asyncio.ensure_future(result)] = name_of(who)
        if not pending:
            return
        done, late = await asyncio.wait(pending, timeout=self.CLOSE_TIMEOUT)
        for task in done:
            if not task.cancelled() and task.exception() is not None:
                logger.error("Shutting %r down failed", pending[task], exc_info=task.exception())
        for task in late:
            logger.warning("Gave up waiting for %r to shut down", pending[task])
            task.cancel()
        if late:
            await asyncio.wait(late, timeout=1.0)

    # === The older tier =============================================================

    async def _recall(self) -> None:
        """
        Pulls the tail of the archive back into the session.

        Called once by :meth:`start`, before anyone can ask for context, so a
        chat reopens where it left off. A backend that cannot recall is not an
        error: it simply has nothing to give back.
        """
        holder = self._first(HookLoad)
        if holder is None:
            return
        try:
            for msg in await holder.load(limit=self.recall):
                self._store.add(msg)
        except Exception:
            logger.error("Loading the older context failed; starting empty", exc_info=True)

    async def locate(self, msg_id: MessageID, name: str) -> Optional[str]:
        """
        Where attachment *name* of message *msg_id* can be opened, or None.

        Granted to peers by ``HookLocate``. The answer is the backend's, from
        whoever declared ``HookLink``; with none, or when it fails, it is None.

        Args:
            msg_id: The message the attachment was kept under.
            name: The attachment's name, as the message's text links to it.

        Returns:
            Optional[str]: A link a browser can open, or None.
        """
        linker = self._first(HookLink)
        if linker is None:
            return None
        try:
            return await linker.link(msg_id, name)
        except Exception:
            logger.error("Linking %s of %s failed", name, msg_id, exc_info=True)
            return None

    async def forget(self, before: Optional[datetime] = None) -> int:
        """
        Drops the messages older than *before*, or all of them, here and in the archive.

        The conversation forgets first, with or without a backend, so
        ``context()`` stops returning them at once; then the backend that
        declared ``HookForget`` drops them from the archive.

        Args:
            before: Keep everything from this moment on; None forgets the lot.

        Returns:
            int: How many the backend dropped, or zero when there is none.
        """
        self._store.forget(before)
        holder = self._first(HookForget)
        if holder is None:
            return 0
        return await holder.forget(before=before)
