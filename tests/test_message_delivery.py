"""How the session hands messages to peers: each delivery on its own task.

A peer may be inside ``answer`` for several questions at once, an ask may come
back to a peer that is still asking, and nested asks stop at ``max_depth``.
"""

import asyncio
import logging
import time
from typing import List

import pytest

from chatinho import (
    LOCAL,
    Ask,
    ChatMessage,
    ChatSession,
    HookAnswer,
    HookAsk,
    HookListen,
    HookSay,
    Reply,
    PeerError,
    ReplyStatus,
    Say,
    connector,
    frontend,
    require,
)
from conftest import Driver, driven


@connector("slow")
@require(HookAnswer)
class _Slow:
    """Answers after 0.3 seconds, whatever it is asked."""

    async def answer(self, msg: ChatMessage) -> Reply:
        await asyncio.sleep(0.3)
        return Reply("slow: %s" % msg.text)


@connector("ear")
@require(HookListen)
class _Ear:
    """Holds what it hears, taking *pause* seconds over the message 'first'."""

    def __init__(self, pause: float = 0.0) -> None:
        self.pause = pause
        self.heard : List[str] = []

    async def listen(self, msg: ChatMessage) -> None:
        if msg.text == "first":
            await asyncio.sleep(self.pause)
        self.heard.append(msg.text)


@require(HookAnswer)
@require(HookAsk)
class _Relay:
    """Answers every question by asking *to*, and counts what it was asked."""

    ask : Ask

    def __init__(self, name: str) -> None:
        self.name  = name
        self.to    = 0
        self.asked = 0

    async def answer(self, msg: ChatMessage) -> Reply:
        self.asked += 1
        return Reply("%s<%s>" % (self.name, await self.ask(self.to, "again")))


def _relays(session: ChatSession, *names: str) -> List[_Relay]:
    """Relays added in a ring: each asks the next, and the last asks the first."""
    relays = [_Relay(name) for name in names]
    ids    = [session.add_connector(relay) for relay in relays]
    for relay, nxt in zip(relays, ids[1:] + ids[:1]):
        relay.to = nxt
    return relays


# === Every delivery runs on its own ================================================

async def test_a_peer_answers_two_questions_at_once():
    session, view = await driven(connectors=[_Slow()])
    started = time.perf_counter()
    answers = await asyncio.gather(view.ask(1, "a"), view.ask(1, "b"))
    elapsed = time.perf_counter() - started
    assert sorted(answers) == ["slow: a", "slow: b"]
    assert elapsed < 0.45, "the two questions took turns: %.2fs" % elapsed
    await session.close()


async def test_order_is_the_order_said():
    ear = _Ear(pause=0.1)
    session, view = await driven(connectors=[ear])
    await view.say("first")
    await view.say("second")
    await session.close()
    assert ear.heard == ["second", "first"], "the slow first should finish last"
    assert view.texts() == ["first", "second"]


async def test_say_returns_before_anyone_heard():
    ear = _Ear(pause=0.3)
    session, view = await driven(connectors=[ear])
    started = time.perf_counter()
    await view.say("first")
    assert time.perf_counter() - started < 0.1
    assert ear.heard == []
    await session.close()
    assert ear.heard == ["first"]


# === Delivery waits for start and finishes at close ================================

async def test_said_before_start_is_heard_after():
    ear     = _Ear()
    view    = Driver()
    session = ChatSession(frontend=view, connectors=[ear])
    await view.say("early")
    await asyncio.sleep(0.01)
    assert ear.heard == []
    await session.start()
    await session.close()
    assert ear.heard == ["early"]


async def test_a_peer_added_after_start_hears_once_started_again():
    session, view = await driven()
    ear = _Ear()
    session.add_connector(ear)
    await view.say("hello")
    await asyncio.sleep(0.01)
    assert ear.heard == []
    await session.start()
    await session.close()
    assert ear.heard == ["hello"]


async def test_close_lets_a_listener_finish():
    ear = _Ear(pause=0.1)
    session, view = await driven(connectors=[ear])
    await view.say("first")
    await session.close()
    assert ear.heard == ["first"]


async def test_close_does_not_hang(caplog):
    @connector("stuck")
    @require(HookAnswer)
    class Stuck:
        async def answer(self, msg: ChatMessage) -> Reply:
            await asyncio.Event().wait()
            return Reply("never")

    session, view = await driven(connectors=[Stuck()])
    session.CLOSE_TIMEOUT = 0.2
    waiting = asyncio.create_task(view.ask(1, "?"))
    await asyncio.sleep(0.01)
    started = time.perf_counter()
    with caplog.at_level(logging.WARNING, logger="chatinho.session"):
        await session.close()
    assert time.perf_counter() - started < 1.0
    assert "Gave up waiting" in caplog.text
    with pytest.raises(RuntimeError, match="the chat closed"):
        await waiting


# === Asks may recurse ==============================================================

async def test_a_asks_b_and_b_asks_a_back():
    @connector("a")
    @require(HookAnswer)
    @require(HookAsk)
    class A:
        ask : Ask

        async def answer(self, msg: ChatMessage) -> Reply:
            if msg.frm == LOCAL:
                return Reply("A<%s>" % await self.ask(2, "what do you think?"))
            return Reply("A again")

    @connector("b")
    @require(HookAnswer)
    @require(HookAsk)
    class B:
        ask : Ask

        async def answer(self, msg: ChatMessage) -> Reply:
            return Reply("B<%s>" % await self.ask(1, "and you?"))

    session, view = await driven(connectors=[A(), B()])
    answer = await asyncio.wait_for(view.ask(1, "hello"), timeout=2)
    assert answer == "A<B<A again>>"
    await session.close()
    assert session._pending == {}


# === Nested asks are bounded =======================================================

async def test_a_loop_stops_at_the_limit():
    session, view = await driven()
    ping, pong = _relays(session, "ping", "pong")
    await session.start()
    # The limit's ERROR reply raises in the relay that asked; none catches it,
    # so each relay's answer fails in turn and the user's ask raises it too.
    with pytest.raises(PeerError, match=r"too many nested asks \(limit 8\)"):
        await asyncio.wait_for(view.ask(ping.peer_id, "go"), timeout=2)
    assert ping.asked + pong.asked == 8
    errors = [m for m in view.context() if m.status == ReplyStatus.ERROR]
    assert [m.text for m in errors] == ["too many nested asks (limit 8)"]
    await session.close()


async def test_the_limit_is_configurable():
    session, view = await driven(max_depth=2)
    a, b, c = _relays(session, "a", "b", "c")
    await session.start()
    with pytest.raises(PeerError, match=r"too many nested asks \(limit 2\)"):
        await asyncio.wait_for(view.ask(a.peer_id, "go"), timeout=2)
    assert (a.asked, b.asked, c.asked) == (1, 1, 0)
    await session.close()


async def test_the_asker_of_a_question_past_the_limit_gets_a_peer_error():
    session, view = await driven(max_depth=1)
    a, b = _relays(session, "a", "b")
    await session.start()
    with pytest.raises(PeerError, match="too many nested asks"):
        await asyncio.wait_for(a.ask(b.peer_id, "go"), timeout=2)
    await session.close()


async def test_unrelated_questions_are_not_nested():
    session, view = await driven(connectors=[_Slow()], max_depth=1)
    assert await view.ask(1, "one") == "slow: one"
    assert await view.ask(1, "two") == "slow: two"
    await session.close()


async def test_listening_is_not_nesting():
    """A peer that asks from listen() asks at depth 1, even hearing an answer.

    The answer is posted from inside the answering task, whose depth a task
    started there inherits; listening must start from zero again.
    """
    @connector("curious")
    @require(HookListen)
    @require(HookAsk)
    class Curious:
        ask : Ask

        def __init__(self) -> None:
            self.answers : List[str] = []

        async def listen(self, msg: ChatMessage) -> None:
            if msg.text == "slow: go":
                self.answers.append(await self.ask(1, "from listen"))

    curious = Curious()
    session, view = await driven(connectors=[_Slow(), curious], max_depth=1)
    await view.say("go")
    await session.close()
    assert curious.answers == ["slow: from listen"]


async def test_replies_traded_past_the_limit_are_dropped():
    """Two peers that answer by saying a reply stop at the limit, without trading errors.

    What ``answer`` returns is never asked of anyone, so the only chain left is
    one a peer builds by *saying* its reply from inside ``answer``.
    """
    @require(HookAnswer)
    @require(HookSay)
    class Chatty:
        say : Say

        def __init__(self, name: str) -> None:
            self.name = name

        async def answer(self, msg: ChatMessage) -> None:
            await self.say("re: %s" % msg.text, reply_to=msg.id)

    session, view = await driven()
    first, second = Chatty("first"), Chatty("second")
    session.add_connector(first)
    to = session.add_connector(second)
    await session.start()
    await first.say("hi", to=to)
    await session.close()
    texts = view.texts()
    assert texts[0] == "hi" and len(texts) == 1 + 8
    assert not [m for m in view.context() if m.status == ReplyStatus.ERROR]


# === An answer is heard, never asked ==============================================

@require(HookAnswer)
@require(HookListen)
@require(HookSay)
class _Chatty:
    """Answers whatever it is asked, and records what it answered and heard."""

    say : Say

    def __init__(self, name: str) -> None:
        self.name     = name
        self.answered : List[str] = []
        self.heard    : List[str] = []

    async def answer(self, msg: ChatMessage) -> Reply:
        self.answered.append(msg.text)
        return Reply("%s: re %s" % (self.name, msg.text))

    async def listen(self, msg: ChatMessage) -> None:
        self.heard.append(msg.text)


async def test_an_answer_to_an_addressed_say_is_heard_not_answered():
    session, view = await driven()
    first, second = _Chatty("first"), _Chatty("second")
    session.add_connector(first)
    to = session.add_connector(second)
    await session.start()
    await first.say("hi", to=to)
    await session.close()
    assert view.texts() == ["hi", "second: re hi"]
    assert first.answered == [] and second.answered == ["hi"]
    assert "second: re hi" in first.heard


async def test_two_answering_peers_do_not_trade_answers():
    """One unprompted say between the only two answering peers costs one answer."""
    session, view = await driven()
    a, b = _Chatty("a"), _Chatty("b")
    session.add_connector(a)
    session.add_connector(b)
    await session.start()
    await a.say("a note")
    await session.close()
    assert a.answered == [] and b.answered == ["a note"]
    assert view.texts() == ["a note", "b: re a note"]


async def test_a_frontend_that_does_not_answer_is_not_asked(caplog):
    @frontend("screen")
    @require(HookSay)
    @require(HookListen)
    class Screen:
        say : Say

        def __init__(self) -> None:
            self.heard : List[str] = []

        async def listen(self, msg: ChatMessage) -> None:
            self.heard.append(msg.text)

    screen  = Screen()
    session = ChatSession(frontend=screen, connectors=[_Slow()])
    await session.start()
    with caplog.at_level(logging.WARNING, logger="chatinho.session"):
        await screen.say("hi", to=1)
        await session.close()
    assert "slow: hi" in screen.heard
    assert "was asked but does not declare" not in caplog.text


# === A resolved reply is heard, not answered ======================================

async def test_a_reply_to_ones_own_ask_is_heard_not_answered():
    """A peer that listens and answers gets the reply to its ask only as a listener."""
    @connector("curious")
    @require(HookListen)
    @require(HookAnswer)
    @require(HookAsk)
    class Curious:
        ask : Ask

        def __init__(self) -> None:
            self.heard    : List[str] = []
            self.answered : List[str] = []

        async def listen(self, msg: ChatMessage) -> None:
            self.heard.append(msg.text)

        async def answer(self, msg: ChatMessage) -> Reply:
            self.answered.append(msg.text)
            return Reply("curious<%s>" % await self.ask(2, "and you?"))

    curious = Curious()
    session, view = await driven(connectors=[curious, _Slow()])
    assert await asyncio.wait_for(view.ask(1, "go"), timeout=2) == "curious<slow: and you?>"
    await session.close()
    assert curious.answered == ["go"]
    assert "slow: and you?" in curious.heard
