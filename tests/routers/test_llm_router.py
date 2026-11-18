"""
LLMRouter against a stubbed AsyncOpenAI: when the model is asked, what it is told, and how it fails.

See src/chatinho/routers/docs/spec.md.
"""

import asyncio
import importlib
import logging
import time
from typing import Callable, List, Optional

import pytest

from chatinho import (
    ChatMessage,
    HookAnswer,
    HookListen,
    HookSay,
    Query,
    Reply,
    Say,
    Secret,
    connector,
    require,
)
from chatinho.support.parts.keys import Env
from chatinho.support.parts.keys.endpoint import Endpoint

from conftest import driven
from fakes.llm import FakeOpenAI, failure, requests

module    = importlib.import_module("chatinho.routers.llm")
LLMRouter = module.LLMRouter


@pytest.fixture(autouse=True)
def fake(monkeypatch):
    FakeOpenAI.reset()
    monkeypatch.setattr(module, "AsyncOpenAI", FakeOpenAI)
    return FakeOpenAI


@connector("peer")
@require(HookAnswer)
class _Peer:
    """Answers whatever it is asked with a fixed text, and records it."""

    def __init__(self, name: str, description: Optional[str] = None, reply: str = "ok") -> None:
        self.name  = name
        if description is not None:
            self.description = description
        self.reply = reply
        self.asked : List[ChatMessage] = []

    async def answer(self, msg: ChatMessage) -> Reply:
        self.asked.append(msg)
        return Reply(self.reply)


@connector("talker")
@require(HookSay)
@require(HookAnswer)
class _Talker:
    """Answers, and says things of its own."""

    say : Say

    def __init__(self) -> None:
        self.asked : List[ChatMessage] = []

    async def answer(self, msg: ChatMessage) -> Reply:
        self.asked.append(msg)
        return Reply("talked")


@connector("ear")
@require(HookListen)
class _Ear:
    """Hears everything, answers nothing."""

    def __init__(self) -> None:
        self.heard : List[str] = []

    async def listen(self, msg: ChatMessage) -> None:
        self.heard.append(msg.text)


def router(**kwargs) -> LLMRouter:
    """A router with its own key, unless the test gives another endpoint."""
    endpoint = kwargs.pop("endpoint", Endpoint(api_key="sk-own", model="router-model"))
    return LLMRouter(endpoint, **kwargs)


async def until(check: Callable[[], bool], what: str) -> None:
    """Waits for *check* to hold, or fails naming *what*."""
    for _ in range(300):
        if check():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("never happened: %s" % what)


def posted(view, msg_id) -> ChatMessage:
    """The message with *msg_id*, as the conversation holds it."""
    return next(m for m in view.context() if m.id == msg_id)


def prompt() -> str:
    """Everything the last request told the model, as one text."""
    return "\n".join(m["content"] for m in requests()[-1]["messages"])


def system() -> str:
    """The system part of the last request."""
    return "\n".join(m["content"] for m in requests()[-1]["messages"] if m["role"] == "system")


def warnings_of(caplog) -> List[str]:
    """The router's warnings."""
    return [r.getMessage() for r in caplog.records
            if r.name == module.__name__ and r.levelno == logging.WARNING]


# === When the model is asked =======================================================

# @ac AC-ROUTE-007.1
async def test_a_reply_goes_back_to_its_author_without_the_model():
    gpt, weather = _Peer("gpt"), _Peer("weather", reply="sunny")
    session, view = await driven(connectors=[gpt, weather], router=router())
    try:
        asked = await view.say("forecast?", to=view.id_of("weather"))
        await until(lambda: any(m.reply_to == asked for m in view.context()), "weather answers")
        answer = next(m for m in view.context() if m.reply_to == asked)
        follow = await view.say("and tomorrow?", reply_to=answer.id)
        await until(lambda: len(weather.asked) == 2, "weather is asked the follow-up")
        assert posted(view, follow).to == view.id_of("weather")
        assert requests() == []
        assert gpt.asked == []
    finally:
        await session.close()


# @ac AC-ROUTE-007.2
async def test_one_answering_peer_is_asked_without_the_model():
    gpt = _Peer("gpt")
    session, view = await driven(connectors=[gpt], router=router())
    try:
        said = await view.say("hello")
        await until(lambda: len(gpt.asked) == 1, "gpt is asked")
        assert posted(view, said).to == view.id_of("gpt")
        assert requests() == []
    finally:
        await session.close()


# @ac AC-ROUTE-007.3
async def test_nobody_to_answer_means_no_model_and_no_route():
    talker = _Talker()
    session, view = await driven(connectors=[talker], router=router())
    try:
        said = await talker.say("thinking aloud")
        assert posted(view, said).to is None
        assert requests() == []
    finally:
        await session.close()


# @ac AC-ROUTE-007.4
async def test_a_real_choice_asks_the_model_once():
    FakeOpenAI.reply = "everyone"
    session, view = await driven(connectors=[_Peer("gpt"), _Peer("weather")], router=router())
    try:
        await view.say("hello")
        assert len(requests()) == 1
    finally:
        await session.close()


# === What the model is told, and how its answer is read ===========================

# @ac AC-ROUTE-008.1
async def test_the_model_names_the_peer_that_answers():
    FakeOpenAI.reply = "  @Weather. "
    gpt, weather = _Peer("gpt"), _Peer("weather")
    session, view = await driven(connectors=[gpt, weather], router=router())
    try:
        said = await view.say("will it rain?")
        assert posted(view, said).to == view.id_of("weather")
        await until(lambda: len(weather.asked) == 1, "weather is asked")
        assert weather.asked[0].id == said
        assert gpt.asked == []
    finally:
        await session.close()


# @ac AC-ROUTE-008.2
async def test_everyone_is_a_broadcast_heard_by_all_and_answered_by_none():
    FakeOpenAI.reply = "Everyone"
    gpt, weather, ear = _Peer("gpt"), _Peer("weather"), _Ear()
    session, view = await driven(connectors=[gpt, weather, ear], router=router())
    try:
        said = await view.say("good morning, all")
        assert posted(view, said).to is None
    finally:
        await session.close()
    assert "good morning, all" in ear.heard
    assert gpt.asked == [] and weather.asked == []


# @ac AC-ROUTE-008.3
async def test_the_model_is_told_the_candidates_the_say_and_what_came_before():
    FakeOpenAI.reply = "everyone"
    gpt, weather = _Peer("gpt", reply="an earlier answer"), _Peer("weather", "Forecasts by city")
    session, view = await driven(connectors=[gpt, weather], router=router())
    try:
        asked = await view.say("an earlier question", to=view.id_of("gpt"))
        await until(lambda: any(m.reply_to == asked for m in view.context()), "gpt answers")
        await view.say("what should I wear?")
        told = prompt()
        assert "gpt" in told and "weather" in told and "Forecasts by city" in told
        assert "what should I wear?" in told
        assert "an earlier question" in told and "an earlier answer" in told
        choices = [line for line in system().splitlines() if line.lstrip().startswith("- ")]
        assert any("weather" in line for line in choices)
        assert not any("driver" in line for line in choices)
    finally:
        await session.close()


# @ac AC-ROUTE-008.3
async def test_a_peer_that_speaks_is_not_offered_its_own_say():
    FakeOpenAI.reply = "everyone"
    talker = _Talker()
    session, view = await driven(connectors=[talker, _Peer("gpt"), _Peer("weather")], router=router())
    try:
        await talker.say("who wants this one?")
        choices = [line.strip() for line in system().splitlines() if line.lstrip().startswith("- ")]
        named   = [line[2:].split(":")[0].strip() for line in choices]
        assert sorted(named) == ["gpt", "weather"]
    finally:
        await session.close()


# @ac AC-ROUTE-008.4
async def test_memory_narrows_what_the_model_is_told():
    FakeOpenAI.reply = "everyone"
    session, view = await driven(connectors=[_Peer("gpt"), _Peer("weather")],
                                 router=router(memory=Query().last(1)))
    try:
        for text in ("first remark", "second remark", "third remark"):
            await view.say(text)
        await view.say("the question")
        told = prompt()
        assert "the question" in told and "third remark" in told
        assert "second remark" not in told and "first remark" not in told
    finally:
        await session.close()


# @ac AC-ROUTE-008.5
async def test_no_memory_tells_the_model_only_the_say():
    FakeOpenAI.reply = "everyone"
    session, view = await driven(connectors=[_Peer("gpt"), _Peer("weather")], router=router(memory=None))
    try:
        await view.say("an earlier remark")
        await view.say("the question")
        told = prompt()
        assert "the question" in told
        assert "an earlier remark" not in told
    finally:
        await session.close()


# === A failed choice is a broadcast ================================================

# @ac AC-ROUTE-009.1
async def test_an_unknown_name_is_a_broadcast(caplog):
    caplog.set_level(logging.WARNING)
    FakeOpenAI.reply = "the plumber"
    gpt, weather = _Peer("gpt"), _Peer("weather")
    session, view = await driven(connectors=[gpt, weather], router=router())
    try:
        said = await view.say("fix the sink")
        assert posted(view, said).to is None
    finally:
        await session.close()
    assert gpt.asked == [] and weather.asked == []
    assert warnings_of(caplog)
    assert not any("fix the sink" in w for w in warnings_of(caplog))


# @ac AC-ROUTE-009.2
async def test_a_name_two_peers_share_is_a_broadcast(caplog):
    caplog.set_level(logging.WARNING)
    FakeOpenAI.reply = "bot"
    one, two = _Peer("bot"), _Peer("bot")
    session, view = await driven(connectors=[one, two], router=router())
    try:
        said = await view.say("which of you?")
        assert posted(view, said).to is None
    finally:
        await session.close()
    assert one.asked == [] and two.asked == []
    assert warnings_of(caplog)


# @ac AC-ROUTE-009.3
async def test_a_failed_request_is_a_broadcast_named_in_the_log(caplog):
    caplog.set_level(logging.WARNING)
    FakeOpenAI.error = failure("APIConnectionError", "connection refused")
    session, view = await driven(connectors=[_Peer("gpt"), _Peer("weather")], router=router())
    try:
        said = await view.say("a private thought")
        assert posted(view, said).to is None
    finally:
        await session.close()
    warned = warnings_of(caplog)
    assert any("APIConnectionError" in w for w in warned)
    assert not any("a private thought" in w for w in warned)


# @ac AC-ROUTE-009.4
async def test_a_slow_model_is_a_broadcast_after_the_timeout(caplog):
    caplog.set_level(logging.WARNING)
    FakeOpenAI.gate = asyncio.Event()                  # never set: the model never answers
    session, view = await driven(connectors=[_Peer("gpt"), _Peer("weather")], router=router(timeout=0.1))
    try:
        started = time.monotonic()
        said    = await view.say("anyone?")
        elapsed = time.monotonic() - started
        assert posted(view, said).to is None
        assert elapsed < 0.5
    finally:
        await session.close()
    assert any("time" in w.lower() for w in warnings_of(caplog))


# @ac AC-ROUTE-009.5
async def test_no_key_is_a_broadcast_naming_the_reference(caplog, monkeypatch):
    caplog.set_level(logging.WARNING)
    monkeypatch.delenv("CHATINHO_ROUTER_TEST_KEY", raising=False)
    endpoint = Endpoint(api_key=Env("CHATINHO_ROUTER_TEST_KEY"), model="router-model")
    peers         = [_Peer("gpt"), _Peer("weather")]
    session, view = await driven(connectors=peers, router=router(endpoint=endpoint))
    try:
        said = await view.say("hello")
        assert posted(view, said).to is None
    finally:
        await session.close()
    assert requests() == []
    assert any("CHATINHO_ROUTER_TEST_KEY" in w for w in warnings_of(caplog))


# @ac AC-ROUTE-009.6
@pytest.mark.parametrize("bad", [0, -1, 0.0])
def test_a_timeout_that_is_not_positive_is_refused(bad):
    with pytest.raises(ValueError):
        router(timeout=bad)


# === Which key asks the model ======================================================

# @ac AC-ROUTE-010.1
async def test_a_lent_key_asks_the_model():
    FakeOpenAI.reply = "everyone"
    session, view = await driven(connectors=[_Peer("gpt"), _Peer("weather")], router=router())
    try:
        await view.say("hello", credentials={"llm": Secret("client-key")})
    finally:
        await session.close()
    used = [c.api_key for c in FakeOpenAI.clients if c.requests]
    assert used == ["client-key"]


# @ac AC-ROUTE-010.2
async def test_its_own_key_is_read_when_first_needed(monkeypatch):
    FakeOpenAI.reply = "everyone"
    monkeypatch.delenv("CHATINHO_ROUTER_LATE_KEY", raising=False)
    endpoint = Endpoint(api_key=Env("CHATINHO_ROUTER_LATE_KEY"), model="router-model")
    peers         = [_Peer("gpt"), _Peer("weather")]
    session, view = await driven(connectors=peers, router=router(endpoint=endpoint))
    try:
        monkeypatch.setenv("CHATINHO_ROUTER_LATE_KEY", "sk-late")
        await view.say("hello")
    finally:
        await session.close()
    used = [c.api_key for c in FakeOpenAI.clients if c.requests]
    assert used == ["sk-late"]
