"""The chat core: peers, messages and the three verbs.

:class:`ChatSession` holds every use case the chat offers and imports no UI
framework, so it can be driven from a TUI, a script or a test without a
terminal.

Everyone in a chat is a **peer** with an integer id. :data:`LOCAL` —
zero — is the user; every connector and every tool is numbered from one. A
peer is a plain class that declares what it can do, and the session
hands the capabilities over at :meth:`attach`.

The conversation is protected: ``_say``, ``_ask``, ``_answer`` and
``_load_messages`` are never called directly. Declaring a hook is the only door
in, and implementing ``on_say`` or ``on_ask`` is the only door out.

Every peer has its own queue and its own task draining it, so a
subsystem that takes a second to answer holds up nobody but itself.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from .chat_hooks import (
    HookForget,
    HookListen,
    HookLoad,
    HookOnAsk,
    HookOnSay,
    declares,
    hooks_of,
    name_of,
)
from .chat_message import ChatMessage, MessageStore

logger = logging.getLogger(__name__)

COMMAND_PREFIX : str = "/"


class ChatSession:
    """Routes messages between peers, and keeps the history.

    The five interfaces onto the conversation are reached only by declaring a
    hook — three the session grants, two it calls:

    - ``HookSay``          grants ``say(text, reply_to=None)``.
    - ``HookAsk``          grants ``ask(to, text)``, which awaits the answer.
    - ``HookOnAsk``        demands ``on_ask(msg)`` and grants ``answer(msg, text)``.
    - ``HookOnSay``        demands ``on_say(msg)``.
    - ``HookContext``      grants ``context(since=, start=, limit=)``.
    - ``HookListen``       demands ``on_listen(msg)`` — every message that crosses.
    """

    def __init__(
        self,
        peers : Optional[List[Any]] = None,
        backend      : Optional[Any] = None,
        recall       : int = 200,
    ) -> None:
        #: Where the conversation goes when it is no longer recent.
        self.backend : Optional[Any] = backend
        #: How much of the archive ``start()`` pulls back into the session.
        self.recall  : int = recall

        self._store    : MessageStore = MessageStore()
        self._by_id    : Dict[int, Any] = {}
        self._queues   : Dict[int, "asyncio.Queue[ChatMessage]"] = {}
        self._tasks    : Dict[int, asyncio.Task] = {}
        self._pending  : Dict[str, "asyncio.Future[str]"] = {}
        self._next_id  : int = 1

        for who in peers or []:
            self.attach(who)
        if backend is not None:
            # A peer like any other: it gets an id and a queue, and it
            # hears the conversation rather than being pushed at. `backend` is
            # only sugar for the role — the session finds what it needs by what
            # the thing declared, not by which parameter it arrived in.
            self.attach(backend)

    # === Peers ===============================================================

    def attach(self, who: Any, at: Optional[int] = None) -> int:
        """Registers *who*, hands over its grants and returns its id.

        The whole plugin contract. An id is assigned unless the caller pins one
        — the presentation pins :data:`LOCAL`, because the user is peer
        zero by definition.

        Args:
            who: Anything declaring hooks.
            at: The id to register it under; assigned when omitted.

        Returns:
            int: The id the peer now answers to.

        Raises:
            ValueError: If *at* is already taken.
        """
        if at is None:
            at = self._next_id
            self._next_id += 1
        elif at in self._by_id:
            raise ValueError("Id %d is already taken by %r" % (at, name_of(self._by_id[at])))

        # peer_id, not id: Textual's DOMNode already owns `id` and validates it
        # as a string. A peer rarely needs its own number anyway — the
        # grants bind `frm` for it — but knowing it costs nothing.
        who.peer_id = at
        self._by_id[at] = who
        self._queues[at] = asyncio.Queue()
        self._grant(who, at)
        self._start(who)
        return at

    def id_of(self, name: str) -> Optional[int]:
        """Returns the id of the peer with that visible name, or None.

        The name is what the chat displays and what the user types after ``/``;
        the id is what messages are addressed to. Keeping them apart is what
        lets a peer be renamed without breaking replies in flight.
        """
        for at, who in self._by_id.items():
            if name_of(who) == name:
                return at
        return None

    def _peers(self) -> Dict[int, Any]:
        """Everyone registered, by id. Granted by ``HookPeers``."""
        return dict(self._by_id)

    def _grant(self, who: Any, at: int) -> None:
        """Sets the attributes *who*'s declared hooks ask for.

        Each grant is bound to the peer's own id, so nobody can speak in
        another's name: the ``frm`` of a message is not an argument.
        """
        grants = {
            "say"           : lambda: self._say_for(at),
            "ask"           : lambda: self._ask_for(at),
            "answer"        : lambda: self._answer_for(at),
            "context"       : lambda: self._context,
            "peers"  : lambda: self._peers,
        }
        for hook in hooks_of(who):
            for granted in hook.grants:
                build = grants.get(granted)
                if build is None:
                    logger.warning("Hook %s asks for unknown grant %r", hook, granted)
                    continue
                setattr(who, granted, build())

    @staticmethod
    def _start(obj: Any) -> None:
        """Calls ``initialize()`` when the object has one."""
        init = getattr(obj, "initialize", None)
        if callable(init):
            init()

    # === The three verbs, bound to one speaker ======================================

    def _say_for(self, frm: int):
        async def say(text: str, *, reply_to: Optional[str] = None) -> str:
            return await self._post(ChatMessage(
                id=self._store.new_id(), text=text, frm=frm, to=None, reply_to=reply_to,
            ))
        return say

    def _ask_for(self, frm: int):
        async def ask(to: int, text: str) -> str:
            if to not in self._by_id:
                raise ValueError("No peer with id %d" % to)
            msg = ChatMessage(id=self._store.new_id(), text=text, frm=frm, to=to)
            future : "asyncio.Future[str]" = asyncio.get_running_loop().create_future()
            self._pending[msg.id] = future
            await self._post(msg)
            return await future
        return ask

    def _answer_for(self, frm: int):
        async def answer(msg: ChatMessage, text: str) -> str:
            return await self._post(ChatMessage(
                id=self._store.new_id(), text=text, frm=frm, to=msg.frm, reply_to=msg.id,
            ))
        return answer

    async def _post(self, msg: ChatMessage) -> str:
        """Keeps *msg* and puts it in the queue of everyone it is for.

        An answer to an ask that is still waiting resolves that wait and goes
        no further: the asker is already holding it.
        """
        self._store.add(msg)
        waiting = self._pending.pop(msg.reply_to, None) if msg.reply_to else None
        if waiting is not None and not waiting.done():
            waiting.set_result(msg.text)
            return msg.id

        # You never hear yourself, whichever way you were listening.
        listeners = {at for at, who in self._by_id.items()
                     if at != msg.frm and declares(who, HookListen)}
        if msg.to is not None:
            audience = {msg.to}
        else:
            audience = {at for at, who in self._by_id.items()
                        if at != msg.frm and declares(who, HookOnSay)}
        for at in listeners | audience:
            queue = self._queues.get(at)
            if queue is not None:
                queue.put_nowait(msg)
        return msg.id

    async def _deliver(self, who: Any, msg: ChatMessage) -> None:
        """Hands one message to one peer, every way it declared to get it.

        The three are not exclusive: something that listens *and* answers gets
        both calls for the same message, because it asked for both.
        """
        if declares(who, HookListen):
            await who.on_listen(msg)

        if msg.is_broadcast:
            if declares(who, HookOnSay):
                await who.on_say(msg)
            return
        if msg.to != getattr(who, "peer_id", None):
            return
        if not declares(who, HookOnAsk):
            logger.warning("%r was asked but does not declare %s", name_of(who), HookOnAsk)
            return
        reply = await who.on_ask(msg)
        if reply is not None:
            await who.answer(msg, reply)

    async def _drain(self, at: int) -> None:
        """One peer's queue, one message at a time.

        A peer that raises is logged and its queue carries on: one bad
        subsystem must not take the chat down, nor stall its own backlog.
        """
        queue = self._queues[at]
        while True:
            msg = await queue.get()
            try:
                await self._deliver(self._by_id[at], msg)
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
        """The conversation so far, by time or by index. Granted by ``HookContext``.

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

    async def start(self) -> None:
        """Starts one drain task per peer.

        Separate from construction because the tasks need a running loop, and a
        session is usually built before there is one.
        """
        await self._recall()
        for at in self._queues:
            if at not in self._tasks or self._tasks[at].done():
                self._tasks[at] = asyncio.create_task(self._drain(at))

    async def close(self) -> None:
        """Stops the drain tasks and shuts every peer down.

        A peer holding a server or a thread would otherwise outlive the
        chat it was serving.
        """
        # Drain before cancelling: a message still in a queue is a message a
        # listener has not held yet, and cancelling first made "the
        # conversation survives" true only sometimes.
        try:
            await asyncio.wait_for(
                asyncio.gather(*(q.join() for q in self._queues.values())), timeout=5.0)
        except asyncio.TimeoutError:
            logger.warning("Gave up waiting for the queues to drain")
        for task in self._tasks.values():
            task.cancel()
        self._tasks.clear()
        for who in list(self._by_id.values()):
            shutdown = getattr(who, "shutdown", None)
            if callable(shutdown):
                try:
                    shutdown()
                except Exception:
                    logger.error("Shutting %r down failed", name_of(who), exc_info=True)

    # === The older tier =============================================================

    async def _recall(self) -> None:
        """Pulls the tail of the archive back into the session.

        Called once by :meth:`start`, before anyone can ask for context, so a
        chat reopens where it left off. A backend that cannot recall is not an
        error: it simply has nothing to give back.
        """
        holder = next((w for w in self._by_id.values() if declares(w, HookLoad)), None)
        if holder is None:
            return
        try:
            for msg in await holder.load(limit=self.recall):
                self._store.add(msg)
        except Exception:
            logger.error("Loading the older context failed; starting empty", exc_info=True)

    async def forget(self, before: Optional[datetime] = None) -> int:
        """Drops archived messages older than *before*, or all of them.

        Args:
            before: Keep everything from this moment on; None forgets the lot.

        Returns:
            int: How many the backend dropped, or zero when it cannot forget.
        """
        holder = next((w for w in self._by_id.values() if declares(w, HookForget)), None)
        if holder is None:
            return 0
        return await holder.forget(before=before)
