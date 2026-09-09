#!/usr/bin/env python3
"""The ten hooks, one example each, in a chat with no terminal.

Every other example shows a chat. This one shows the *declarations* — what each
hook demands, what it grants, and what actually arrives at each door — by
running a short conversation past a peer for every hook and printing what it
saw. It is the runnable half of ``docs/SPEC.md``; if the two ever disagree, this
file is the one that is right, because it executes.

Run it::

    python examples/hooks.py

Nothing here needs a terminal, a network or a database: the archive is a list.
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Optional

from chatinho import (
    LOCAL,
    TOOL,
    Ask,
    ChatMessage,
    ChatSession,
    Context,
    HookAnswer,
    HookAsk,
    HookContext,
    HookExecute,
    HookForget,
    HookInvoke,
    HookListen,
    HookLoad,
    HookPeers,
    HookSay,
    Invoke,
    Peers,
    Say,
    backend,
    connector,
    require,
    tool,
)


def note(hook: str, what: str) -> None:
    """Prints one line, tagged with the hook that caused it."""
    print("   %-12s %s" % (hook, what))


# === The grants: what a peer may do =============================================
#
# A class that declares only grants is asked for nothing. This is the shape of a
# presentation — the terminal in demo.py and headless.py declare exactly these,
# plus the two demands below.


@require(HookSay)       # say(text, reply_to=None) -> id
@require(HookAsk)       # await ask(to, text)      -> the answer
@require(HookInvoke)    # await invoke(name, args) -> what the command answered
@require(HookContext)   # context(since=, start=, limit=) -> the conversation
@require(HookPeers)     # peers() -> {id: peer}
class Screen:
    """The presentation, attached at ``LOCAL``: peer zero, and nothing special.

    Annotate every grant, or a type checker cannot see it: the session sets them
    with ``setattr`` at ``attach``, so nothing in the class body declares them.
    """

    say     : Say
    ask     : Ask
    invoke  : Invoke
    context : Context
    peers   : Peers


# === The demands: what a peer must write ========================================


@connector("echo")
@require(HookListen)
@require(HookSay)
class EchoConnector:
    """``HookListen`` demands ``listen(msg)``: every message that crosses.

    Every one — a say, an ask, the answer to it, a command being run and what it
    answered, whoever it was for. A peer that only wants what was said to the
    room checks ``msg.is_broadcast``, and this one does: without that it would
    reply to a ``/upper`` the user typed.

    You never hear yourself, which is what stops this from answering forever.
    """

    say : Say

    async def listen(self, msg: ChatMessage) -> None:
        """Sees everything; answers only what the user said to the room."""
        note("HookListen", "heard from=%d to=%s %r" % (msg.frm, msg.to, msg.text))
        if not msg.is_broadcast or not msg.is_local:
            return                      # an ask, a command, or TOOL — not for it
        await self.say("echo: %s" % msg.text, reply_to=msg.id)


@connector("weather")
@require(HookAnswer)
class WeatherConnector:
    """``HookAnswer`` demands ``answer(msg)``: someone asked *you*.

    What it returns is the reply, posted by the session in this peer's name.
    Returning ``None`` is not a failure — the ask stays waiting, and whatever
    this peer says later with ``reply_to`` set resolves it. There is no separate
    grant for answering late; ``say(text, reply_to=msg.id)`` is that door.
    """

    async def answer(self, msg: ChatMessage) -> Optional[str]:
        """Answers inline."""
        note("HookAnswer", "was asked %r" % msg.text)
        return "sunny"


@tool("upper", "Upper-case the rest of the line")
@require(HookExecute)
class UpperCommand:
    """``HookExecute`` demands ``execute(args, by)``: what a command *is*.

    A command is not a peer — no id, no queue, nothing addressed to it. What it
    returns is the answer: the session posts it in ``TOOL``'s name, replying to
    the invocation, so a command that should be seen just returns. Declare
    ``HookSay`` as well only for what *differs* from the answer — progress while
    it works. Saying and returning the same text writes it twice.
    """

    async def execute(self, args: str = "", by: int = LOCAL, **kwargs) -> str:
        """Answers with *args* in upper case.

        Args:
            args: The rest of the line.
            by: The id of the peer that ran it, so a command may answer
                differently depending on who asked.
            **kwargs: Ignored.

        Returns:
            str: The answer, which the session posts as ``TOOL``.
        """
        del kwargs
        note("HookExecute", "run by %d with %r" % (by, args))
        return args.upper()


@backend("archive")
@require(HookListen)    # to hear the conversation
@require(HookLoad)      # to give it back at start()
@require(HookForget)    # to drop it
class ListArchive:
    """The three hooks a backend declares, over a list instead of a database.

    The backend is not a key-value store and nothing pushes at it: it is a peer
    that listens. ``DatabaseBackend`` is this, with SQLAlchemy in an executor.
    """

    def __init__(self, seeded: Optional[List[ChatMessage]] = None) -> None:
        self.kept : List[ChatMessage] = list(seeded or [])

    async def listen(self, msg: ChatMessage) -> None:
        """Keeps every message that crosses the session."""
        note("· archive", "kept from=%d to=%s %r" % (msg.frm, msg.to, msg.text))
        self.kept.append(msg)

    async def load(self, since: Optional[datetime] = None,
                   limit: Optional[int] = None) -> List[ChatMessage]:
        """Gives the older context back. Called once, by ``start()``.

        Args:
            since: Only messages at or after this moment, when given.
            limit: At most this many, newest kept.

        Returns:
            List[ChatMessage]: What the chat reopens with.
        """
        del since, limit
        note("HookLoad", "gave back %d from before" % len(self.kept))
        return list(self.kept)

    async def forget(self, before: Optional[datetime] = None) -> int:
        """Drops what was held.

        Args:
            before: Only messages older than this, when given.

        Returns:
            int: How many were dropped.
        """
        del before
        dropped, self.kept = len(self.kept), []
        note("HookForget", "dropped %d" % dropped)
        return dropped


# === Running the whole of it ====================================================


async def main() -> None:
    """Drives one message of every kind past every hook."""
    yesterday = datetime.now() - timedelta(days=1)
    seeded    = [ChatMessage(id="old-1", text="said yesterday", frm=LOCAL, timestamp=yesterday)]

    session = ChatSession(
        connectors = [EchoConnector(), WeatherConnector()],
        commands   = [UpperCommand()],
        backend    = ListArchive(seeded),
    )
    screen = Screen()
    session.attach(screen, at=LOCAL)        # the presentation is peer zero

    print("\n-- start(): HookLoad runs before anyone can ask for context --")
    await session.start()

    # Hearing is queued: a listener sees a message shortly after it was said,
    # not during. The pauses below are only so each step's lines land under its
    # own heading — nothing in the library needs them.
    async def settle() -> None:
        await asyncio.sleep(0.05)

    print("\n-- say: everyone but the speaker --")
    await screen.say("good morning")
    await settle()

    print("\n-- ask: one peer, and it owes a reply --")
    print("   →", await screen.ask(session.id_of("weather"), "what is the weather?"))
    await settle()

    print("\n-- invoke: a command runs, and the running is recorded --")
    print("   →", await screen.invoke("upper", "nothing is hidden"))
    await settle()

    print("\n-- peers: who is here, by id --")
    print("   →", {at: getattr(who, "name", type(who).__name__)
                   for at, who in screen.peers().items()})

    print("\n-- context: one window over both tiers --")
    for msg in screen.context():
        where = {None: "everyone", TOOL: "a command", LOCAL: "the user"}.get(msg.to, str(msg.to))
        print("   from=%-3d to=%-10s %r" % (msg.frm, where, msg.text))

    print("\n-- forget: the archive drops what it held --")
    print("   →", await session.forget(), "dropped")

    await session.close()                   # drains every queue, then shuts down
    print("\n-- close() drained the queues: the last lines above are why --")


if __name__ == "__main__":
    asyncio.run(main())
