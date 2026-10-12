"""OpenAIConnector against a stubbed AsyncOpenAI: memory, keys, failures, no blocking.

See openspec/specs/openai-connector.
"""

import asyncio
import logging
from typing import List

import pytest

from chatinho import SELF, ChatMessage, HookListen, HookSay, Query, ReplyStatus, Say, Secret
from chatinho import connector, require
from chatinho.connectors import openai as module
from chatinho.connectors.openai import OpenAIConnector

from conftest import driven
from llm_kit import FakeOpenAI, failure, requests, sent


@pytest.fixture(autouse=True)
def fake(monkeypatch):
    FakeOpenAI.reset()
    monkeypatch.setattr(module, "AsyncOpenAI", FakeOpenAI)
    return FakeOpenAI


async def reply_to(view, said) -> ChatMessage:
    """Waits for the message that replies to *said*."""
    for _ in range(200):
        for m in view.context():
            if m.reply_to == said:
                return m
        await asyncio.sleep(0.01)
    raise AssertionError("no reply to %s" % said)


@connector("coder")
@require(HookSay)
class Coder:
    say : Say


@connector("bystander")
@require(HookListen)
class Bystander:
    def __init__(self) -> None:
        self.heard : List[str] = []

    async def listen(self, msg: ChatMessage) -> None:
        self.heard.append(msg.text)


# === Answering never blocks the chat ==============================================

async def test_the_models_text_is_the_answer():
    session, view = await driven(connectors=[OpenAIConnector(name="gpt", api_key="sk-own")])
    try:
        reply = await reply_to(view, await view.say("weather?"))
        assert (reply.text, reply.status) == ("Sunny", ReplyStatus.ANSWERED)
    finally:
        await session.close()


async def test_the_chat_keeps_moving_while_the_model_thinks():
    FakeOpenAI.gate = asyncio.Event()
    coder, bystander = Coder(), Bystander()
    session, view = await driven(connectors=[OpenAIConnector(name="gpt", api_key="sk-own"), coder, bystander])
    try:
        said = await view.say("think hard", to=view.id_of("gpt"))
        while not requests():
            await asyncio.sleep(0.01)
        await coder.say("meanwhile")
        for _ in range(100):
            if "meanwhile" in bystander.heard:
                break
            await asyncio.sleep(0.01)
        assert "meanwhile" in bystander.heard
        assert not any(m.reply_to == said for m in view.context())
        FakeOpenAI.gate.set()
        assert (await reply_to(view, said)).text == "Sunny"
    finally:
        FakeOpenAI.gate.set()
        await session.close()


# === Endpoint, model and system prompt ============================================

async def test_a_system_prompt_leads():
    gpt = OpenAIConnector(name="gpt", api_key="k", system="You review code.")
    session, view = await driven(connectors=[gpt])
    try:
        await reply_to(view, await view.say("look"))
        assert sent()[0] == {"role": "system", "content": "You review code."}
    finally:
        await session.close()


async def test_model_temperature_max_tokens_and_endpoint():
    gpt = OpenAIConnector(name="gpt", api_key="k", model="m-1", temperature=0.1, max_tokens=50,
                          base_url="http://localhost:11434/v1")
    session, view = await driven(connectors=[gpt])
    try:
        await reply_to(view, await view.say("hi"))
        request = requests()[-1]
        assert (request["model"], request["temperature"], request["max_tokens"]) == ("m-1", 0.1, 50)
        assert FakeOpenAI.clients[-1].base_url == "http://localhost:11434/v1"
    finally:
        await session.close()


# === The conversation is remembered ===============================================

async def test_a_follow_up_question():
    session, view = await driven(connectors=[OpenAIConnector(name="gpt", api_key="k")])
    try:
        FakeOpenAI.reply = "Hi Ana"
        await reply_to(view, await view.say("My name is Ana"))
        FakeOpenAI.reply = "Ana"
        await reply_to(view, await view.say("What is my name?"))
        assert sent() == [
            {"role": "user",      "content": "My name is Ana"},
            {"role": "assistant", "content": "Hi Ana"},
            {"role": "user",      "content": "What is my name?"},
        ]
    finally:
        await session.close()


def room(reviewer: OpenAIConnector, coder: Coder) -> list:
    """Two answering peers, so a say to everyone stays a broadcast."""
    return [reviewer, OpenAIConnector(name="other", api_key="k"), coder]


async def test_another_peer_is_named():
    coder    = Coder()
    reviewer = OpenAIConnector(name="reviewer", api_key="k", memory=Query(errors=False))
    session, view = await driven(connectors=room(reviewer, coder))
    try:
        await coder.say("def f(): pass")
        await reply_to(view, await view.say("review it", to=view.id_of("reviewer")))
        assert sent() == [
            {"role": "user", "content": "coder: def f(): pass"},
            {"role": "user", "content": "review it"},
        ]
    finally:
        await session.close()


async def test_only_its_own_exchanges_by_default():
    coder    = Coder()
    reviewer = OpenAIConnector(name="reviewer", api_key="k")
    session, view = await driven(connectors=room(reviewer, coder))
    try:
        await coder.say("def f(): pass")
        await reply_to(view, await view.say("review it", to=view.id_of("reviewer")))
        assert sent() == [{"role": "user", "content": "review it"}]
    finally:
        await session.close()


async def test_no_memory():
    session, view = await driven(connectors=[OpenAIConnector(name="gpt", api_key="k", memory=None)])
    try:
        await reply_to(view, await view.say("one"))
        await reply_to(view, await view.say("two"))
        assert sent() == [{"role": "user", "content": "two"}]
    finally:
        await session.close()


async def test_memory_is_bounded_and_skips_errors():
    gpt = OpenAIConnector(name="gpt", api_key="k", memory=Query(peer=SELF, errors=False).last(2))
    session, view = await driven(connectors=[gpt])
    try:
        FakeOpenAI.error = failure("APIConnectionError")
        await reply_to(view, await view.say("first"))
        FakeOpenAI.error = None
        await reply_to(view, await view.say("second"))
        await reply_to(view, await view.say("third"))
        contents = [m["content"] for m in sent()]
        assert contents == ["second", "Sunny", "third"]
        assert all("could not get an answer" not in c for c in contents)
    finally:
        await session.close()


# === A lent key wins over the configured one ======================================

async def test_answered_with_the_askers_key():
    session, view = await driven(connectors=[OpenAIConnector(name="gpt", api_key="sk-own")])
    try:
        await reply_to(view, await view.say("one", credentials={"llm": Secret("sk-lent")}))
        await reply_to(view, await view.say("two"))
        keys = [c.api_key for c in FakeOpenAI.clients if c.requests]
        assert keys == ["sk-lent", "sk-own"]
        lent = next(c for c in FakeOpenAI.clients if c.api_key == "sk-lent")
        assert lent.closed
    finally:
        await session.close()


async def test_no_key_at_all():
    session, view = await driven(connectors=[OpenAIConnector(name="gpt")])
    try:
        reply = await reply_to(view, await view.say("hello"))
        assert reply.status == ReplyStatus.ERROR
        assert "no API key" in reply.text and "'llm'" in reply.text
        assert requests() == []
    finally:
        await session.close()


# === Failures are answers, and starting needs no network ==========================

async def test_starting_without_a_key_makes_no_request():
    session, _ = await driven(connectors=[OpenAIConnector(name="gpt")])
    try:
        assert FakeOpenAI.clients == []
    finally:
        await session.close()


async def test_a_lent_key_never_reaches_the_reply_or_the_logs(caplog):
    FakeOpenAI.error = failure("AuthenticationError", "bad key sk-lent")
    session, view = await driven(connectors=[OpenAIConnector(name="gpt")])
    try:
        with caplog.at_level(logging.DEBUG):
            reply = await reply_to(view, await view.say("hello", credentials={"llm": Secret("sk-lent")}))
        assert reply.status == ReplyStatus.ERROR
        assert "sk-lent" not in reply.text
        assert "sk-lent" not in caplog.text
    finally:
        await session.close()


async def test_the_endpoint_refuses(caplog):
    FakeOpenAI.error = failure("AuthenticationError", "bad key sk-secret")
    session, view = await driven(connectors=[OpenAIConnector(name="gpt", api_key="sk-secret")])
    try:
        with caplog.at_level(logging.DEBUG):
            reply = await reply_to(view, await view.say("hello"))
        assert reply.status == ReplyStatus.ERROR
        assert reply.text == "gpt: could not get an answer (AuthenticationError)"
        assert "sk-secret" not in caplog.text
    finally:
        await session.close()
