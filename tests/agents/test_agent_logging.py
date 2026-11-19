"""
Tests for what an agent peer logs: each run, how long it took and how it went, and each build.

The model is scripted (``fakes.agent``).
"""

import logging
from typing import Any, Dict, FrozenSet, List

import pytest
from langchain.agents import create_agent

from chatinho.support.kits.agent import AgentPeer
from conftest import driven
from fakes.agent import fake, says


@pytest.fixture(autouse=True)
def everything(caplog):
    caplog.set_level(logging.DEBUG, logger="chatinho")
    return caplog


class _Factory:
    name    : str            = "plain"
    options : FrozenSet[str] = frozenset({"name", "system_prompt"})
    covered : FrozenSet[str] = frozenset()

    async def build(self, model: Any, tools: List[Any], options: Dict[str, Any], peer: Any) -> Any:
        return create_agent(model, tools=tools, **options)


def having(caplog, *words: str) -> List[str]:
    return [r.getMessage() for r in caplog.records
            if r.name.startswith("chatinho") and all(w in r.getMessage() for w in words)]


def question_id(view, text: str):
    return next(m.id for m in view.context() if m.text == text)


# @ac AC-AGENT-013.1
async def test_a_run_is_logged_with_how_long_it_took(caplog):
    dev = AgentPeer("dev", fake(says("It is sunny.")), _Factory())
    session, view = await driven(connectors=[dev])
    await view.ask(dev.peer_id, "rain?")
    await session.close()
    assert having(caplog, "dev", str(question_id(view, "rain?")), "took", "answered")


# @ac AC-AGENT-013.2
async def test_a_run_that_fails_is_logged_with_the_errors_type(caplog):
    model       = fake(says("never"))
    model.error = ValueError("the model broke")
    dev = AgentPeer("dev", model, _Factory())
    session, view = await driven(connectors=[dev])
    await view.ask(dev.peer_id, "rain?")
    await session.close()
    assert having(caplog, str(question_id(view, "rain?")), "ValueError")


# @ac AC-AGENT-013.3
async def test_the_first_question_builds_the_agent_and_says_so(caplog):
    dev = AgentPeer("dev", fake(says("It is sunny.")), _Factory())
    session, view = await driven(connectors=[dev])
    assert not having(caplog, "built")
    await view.ask(dev.peer_id, "rain?")
    await session.close()
    built = having(caplog, "dev", "built", "plain")
    assert built
    assert any(" tools" in line for line in built)


# @ac AC-AGENT-013.4
async def test_no_text_is_logged(caplog):
    dev = AgentPeer("dev", fake(says("ANSWER-zebra")), _Factory())
    session, view = await driven(connectors=[dev])
    await view.ask(dev.peer_id, "QUESTION-zebra")
    await session.close()
    every = "\n".join(r.getMessage() for r in caplog.records)
    assert "ANSWER-zebra" not in every
    assert "QUESTION-zebra" not in every
    assert having(caplog, "dev", "took")
