"""
Tests for what the connectors log of each request: who, for which message, to what, how long, how it went.
"""

import logging
from typing import List

import pytest

from chatinho import Secret
from chatinho.support.kits.model import endpoint as model_kit
from chatinho.connectors.mcp import McpConnector
from chatinho.connectors.openai import OpenAIConnector
from chatinho.support.parts.keys.endpoint import Endpoint
from conftest import driven
from fakes.llm import FakeOpenAI, failure
from fakes.mcp import Weather, remote


@pytest.fixture(autouse=True)
def everything(caplog):
    caplog.set_level(logging.DEBUG, logger="chatinho")
    return caplog


@pytest.fixture
def fake(monkeypatch):
    FakeOpenAI.reset()
    monkeypatch.setattr(model_kit, "AsyncOpenAI", FakeOpenAI)
    return FakeOpenAI


def having(caplog, *words: str) -> List[str]:
    return [r.getMessage() for r in caplog.records
            if r.name.startswith("chatinho") and all(w in r.getMessage() for w in words)]


def question_id(view, text: str):
    return next(m.id for m in view.context() if m.text == text)


# @ac AC-CONN-025.1
async def test_a_model_that_answers_is_logged(fake, caplog):
    gpt = OpenAIConnector("gpt", Endpoint(api_key="k", model="m-1"))
    session, view = await driven(connectors=[gpt])
    await view.ask(gpt.peer_id, "rain?")
    await session.close()
    assert having(caplog, "gpt", str(question_id(view, "rain?")), "m-1", "took", "answered")


# @ac AC-CONN-025.2
async def test_a_model_that_fails_is_logged_with_the_errors_type(fake, caplog):
    fake.error = failure("RateLimitError", "quota exceeded")
    gpt = OpenAIConnector("gpt", Endpoint(api_key="k", model="m-1"))
    session, view = await driven(connectors=[gpt])
    await view.ask(gpt.peer_id, "rain?")
    await session.close()
    assert having(caplog, str(question_id(view, "rain?")), "RateLimitError")


# @ac AC-CONN-025.3
async def test_a_remote_session_that_answers_is_logged(caplog):
    remote_session, front = await remote(Weather(), name="office")
    lab = McpConnector(server=front.server, name="lab")
    session, view = await driven(connectors=[lab])
    await view.ask(lab.peer_id, "rain?")
    await session.close()
    await remote_session.close()
    assert having(caplog, "lab", str(question_id(view, "rain?")), "office", "took", "answered")


# @ac AC-CONN-025.4
async def test_no_text_and_no_key_is_logged(fake, caplog):
    fake.reply = "ANSWER-zebra"
    gpt = OpenAIConnector("gpt", Endpoint(api_key="sk-OWN-zebra", model="m-1"))
    session, view = await driven(connectors=[gpt])
    await view.say("QUESTION-zebra", credentials={"llm": Secret("sk-LENT-zebra")})
    await view.ask(gpt.peer_id, "QUESTION-two-zebra")
    await session.close()
    every = "\n".join(r.getMessage() for r in caplog.records)
    for text in ("ANSWER-zebra", "QUESTION-zebra", "QUESTION-two-zebra", "sk-OWN-zebra", "sk-LENT-zebra"):
        assert text not in every, text
    assert having(caplog, "gpt", "took")


class _Failing:
    """A client onto a server whose every call fails with a message holding the conversation."""

    protocol_version   = "2026-07-28"         # modern, so the failure is the call's own
    server_info        = None
    server_capabilities = None

    async def __aenter__(self) -> "_Failing":
        return self

    async def __aexit__(self, *exc) -> None:
        return None

    async def call_tool(self, *args, **kwargs):
        raise RuntimeError("the remote said: QUESTION-remote-zebra")


# @ac AC-CONN-025.4
async def test_a_remote_error_s_text_is_not_logged(caplog):
    """A failed ask is logged by the error's type, never its message (found in review, R3)."""
    remote_session, front = await remote(Weather(), name="office")
    lab = McpConnector(server=front.server, name="lab", peer="weather")
    lab._client = _Failing()
    session, view = await driven(connectors=[lab])
    reply = await view.ask(lab.peer_id, "QUESTION-remote-zebra")
    await session.close()
    await remote_session.close()
    assert reply.status.value == "error"
    every = "\n".join(r.getMessage() for r in caplog.records)
    assert "QUESTION-remote-zebra" not in every
    assert having(caplog, "lab", "RuntimeError")
