"""AgentConnector: a LangChain agent as a peer, with the chat as its tools.

Every agent here runs on a scripted model (``fakes.agent``), so no key and no
network: the script decides each call from the messages of that run alone.
"""

import asyncio
import json
from typing import List

import pytest
from langchain.agents.structured_output import ToolStrategy
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import BaseModel

from chatinho import (
    Ask,
    ChatMessage,
    ChatSession,
    Endpoint,
    HelpCommand,
    HookAnswer,
    HookAsk,
    LOCAL,
    Reply,
    ReplyStatus,
    connector,
    require,
)
from chatinho.connectors import agent as module
from chatinho.connectors.agent import AgentConnector
from chatinho.keys import Env

from fakes.agent import calls, fake, question, says
from conftest import driven


@require(HookAnswer)
class _Echo:
    """A peer that answers '<name>: <question>'."""

    def __init__(self, name: str = "coder") -> None:
        self.name = name

    async def answer(self, msg: ChatMessage) -> Reply:
        return Reply("%s: %s" % (self.name, msg.text))


@connector("broken")
@require(HookAnswer)
class _Broken:
    async def answer(self, msg: ChatMessage) -> Reply:
        raise RuntimeError("kaboom")


async def _asked(view, agent, text: str) -> ChatMessage:
    """Asks the agent and returns its reply message, status included."""
    await view.ask(agent.peer_id, text)
    return next(m for m in reversed(view.context()) if m.frm == agent.peer_id)


def weather(city: str) -> str:
    """The weather in a city."""
    return "sunny in %s" % city


# === Built from create_agent's parameters ==========================================

async def test_options_reach_create_agent():
    model = fake(says("Hi."))
    agent = AgentConnector("agent", model, system_prompt="Be brief.")
    assert model.sent == [], "creating it called the model"
    session, view = await driven(connectors=[agent])
    assert await view.ask(agent.peer_id, "hello") == "Hi."
    first = model.sent[0][0]
    assert isinstance(first, SystemMessage) and first.content == "Be brief."
    await session.close()


def test_an_unknown_option():
    with pytest.raises(TypeError, match="temprature"):
        AgentConnector("agent", fake(says("x")), temprature=0.2)


def test_the_key_is_not_on_the_connector():
    agent = AgentConnector("agent", fake(says("x")))
    assert "api_key" not in vars(agent) and repr(agent) == "AgentConnector(name='agent')"


# === One question, one run of the agent ============================================

async def test_the_last_message_is_the_answer():
    model = fake(calls("weather", city="Porto", then=lambda result: "It is %s." % result))
    agent = AgentConnector("agent", model, tools=[weather])
    session, view = await driven(connectors=[agent])
    assert await view.ask(agent.peer_id, "Weather?") == "It is sunny in Porto."
    await session.close()


async def test_text_blocks_are_joined():
    blocks = [{"type": "text", "text": "Hello, "}, {"type": "text", "text": "Ana."}]
    agent = AgentConnector("agent", fake(lambda messages: AIMessage(content=blocks)))
    session, view = await driven(connectors=[agent])
    assert await view.ask(agent.peer_id, "hi") == "Hello, Ana."
    await session.close()


async def test_a_structured_answer():
    class Forecast(BaseModel):
        city : str
        sky  : str

    model = fake(calls("Forecast", city="Porto", sky="sunny"))
    agent = AgentConnector("agent", model, response_format=ToolStrategy(Forecast))
    session, view = await driven(connectors=[agent])
    assert json.loads(await view.ask(agent.peer_id, "Weather?")) == {"city": "Porto", "sky": "sunny"}
    await session.close()


async def test_the_model_fails():
    model = fake(says("never"))
    model.error = RuntimeError("the prompt was secret")
    agent = AgentConnector("agent", model)
    session, view = await driven(connectors=[agent])
    reply = await _asked(view, agent, "hi")
    assert reply.status == ReplyStatus.ERROR
    assert reply.text == "agent: could not answer (RuntimeError)"
    await session.close()


async def test_two_questions_at_once():
    agent = AgentConnector("agent", fake(lambda messages: AIMessage(content="re: " + question(messages))))
    session, view = await driven(connectors=[agent])
    answers = await asyncio.gather(view.ask(agent.peer_id, "one"), view.ask(agent.peer_id, "two"))
    assert sorted(answers) == ["re: one", "re: two"]
    await session.close()


# === The chat as tools =============================================================

async def test_asking_another_peer():
    model = fake(calls("ask_coder", question="Write a test"))
    agent = AgentConnector("agent", model)
    session, view = await driven(connectors=[agent, _Echo("coder")])
    assert await view.ask(agent.peer_id, "go") == "coder: Write a test"
    asked = [m for m in view.context() if m.frm == agent.peer_id and m.reply_to is None]
    assert [m.text for m in asked] == ["Write a test"]
    await session.close()


async def test_running_a_command():
    model = fake(calls("run_help"))
    agent = AgentConnector("agent", model)
    session, view = await driven(connectors=[agent], commands=[HelpCommand()])
    assert "/help" in await view.ask(agent.peer_id, "what can you do?")
    await session.close()


async def test_never_itself_never_the_user_by_default():
    model = fake(says("ok"))
    agent = AgentConnector("agent", model)
    session, view = await driven(connectors=[agent, _Echo("coder")], commands=[HelpCommand()])
    await view.ask(agent.peer_id, "hi")
    assert model.tools[-1] == ["ask_coder", "run_help"]
    await session.close()


async def test_ask_user_when_asked_for():
    model = fake(calls("ask_user", question="Which city?", then=lambda result: "In " + result))
    agent = AgentConnector("agent", model, ask_user=True)
    session, view = await driven(connectors=[agent])
    view.answers.append("Porto")
    assert await view.ask(agent.peer_id, "Weather?") == "In Porto"
    assert "ask_user" in model.tools[-1]
    await session.close()


async def test_limited_to_the_listed_peers_and_commands():
    model = fake(says("ok"))
    agent = AgentConnector("agent", model, peers=["coder"], commands=[])
    session, view = await driven(connectors=[agent, _Echo("coder"), _Echo("lab")],
                                 commands=[HelpCommand()])
    await view.ask(agent.peer_id, "hi")
    assert model.tools[-1] == ["ask_coder"]
    await session.close()


async def test_a_peer_joins_later():
    model = fake(says("ok"))
    agent = AgentConnector("agent", model)
    session, view = await driven(connectors=[agent, _Echo("coder")])
    await view.ask(agent.peer_id, "first")
    session.add_connector(_Echo("lab"))
    await session.start()
    await view.ask(agent.peer_id, "second")
    assert model.tools == [["ask_coder"], ["ask_coder", "ask_lab"]]
    await session.close()


async def test_names_are_made_safe_and_kept_apart():
    model = fake(says("ok"))
    agent = AgentConnector("agent", model)
    session, view = await driven(connectors=[agent, _Echo("my coder"), _Echo("my_coder")])
    await view.ask(agent.peer_id, "hi")
    assert model.tools[-1] == ["ask_my_coder", "ask_my_coder_2"]
    await session.close()


async def test_the_callers_tool_wins(caplog):
    def ask_coder(question: str) -> str:
        """The caller's own coder."""
        return "mine"

    model = fake(calls("ask_coder", question="x"))
    agent = AgentConnector("agent", model, tools=[ask_coder])
    session, view = await driven(connectors=[agent, _Echo("coder")])
    assert await view.ask(agent.peer_id, "go") == "mine"
    assert model.tools[-1] == ["ask_coder"]
    assert "hides the chat's" in caplog.text
    await session.close()


async def test_a_failing_peer():
    model = fake(calls("ask_broken", question="x", then=lambda result: "It said: " + result))
    agent = AgentConnector("agent", model)
    session, view = await driven(connectors=[agent, _Broken()])
    assert await view.ask(agent.peer_id, "go") == "It said: broken failed: RuntimeError"
    await session.close()


async def test_built_once_for_two_first_questions(monkeypatch):
    built = []
    real  = module.create_agent

    def counting(*args, **kwargs):
        built.append(1)
        return real(*args, **kwargs)

    monkeypatch.setattr(module, "create_agent", counting)
    agent = AgentConnector("agent", fake(says("ok")))
    session, view = await driven(connectors=[agent])
    await asyncio.gather(view.ask(agent.peer_id, "one"), view.ask(agent.peer_id, "two"))
    await view.ask(agent.peer_id, "three")
    assert built == [1]
    await session.close()


# === Recursion through tools =======================================================

async def test_asked_back():
    @connector("coder")
    @require(HookAnswer)
    @require(HookAsk)
    class Coder:
        ask : Ask

        async def answer(self, msg: ChatMessage) -> Reply:
            return Reply("coder<%s>" % await self.ask(1, "and you?"))

    def script(messages):
        if question(messages) == "and you?":
            return AIMessage(content="agent again")
        return calls("ask_coder", question="what do you think?")(messages)

    agent = AgentConnector("agent", fake(script))
    session, view = await driven(connectors=[agent, Coder()])
    assert agent.peer_id == 1
    answer = await asyncio.wait_for(view.ask(agent.peer_id, "go"), timeout=5)
    assert answer == "coder<agent again>"
    await session.close()


async def test_a_loop_of_agents_stops_at_max_depth():
    ping = AgentConnector("ping", fake(calls("ask_pong", question="again")), peers=["pong"])
    pong = AgentConnector("pong", fake(calls("ask_ping", question="again")), peers=["ping"])
    session, view = await driven(connectors=[ping, pong], max_depth=4)
    answer = await asyncio.wait_for(view.ask(ping.peer_id, "go"), timeout=5)
    assert answer == "too many nested asks (limit 4)"
    await session.close()


# === Memory comes from the chat ====================================================

async def test_it_remembers_the_conversation():
    model = fake(lambda messages: AIMessage(content="noted: " + question(messages)))
    agent = AgentConnector("agent", model)
    session, view = await driven(connectors=[agent])
    await view.ask(agent.peer_id, "My name is Ana")
    await view.ask(agent.peer_id, "What is my name?")
    second = model.sent[-1]
    assert [type(m) for m in second] == [HumanMessage, AIMessage, HumanMessage]
    assert [m.content for m in second] == ["My name is Ana", "noted: My name is Ana", "What is my name?"]
    await session.close()


async def test_its_tool_calls_are_not_memory():
    def script(messages):
        if question(messages) == "first":
            return calls("ask_coder", question="help me")(messages)
        return AIMessage(content="second answer")

    model = fake(script)
    agent = AgentConnector("agent", model)
    session, view = await driven(connectors=[agent, _Echo("coder")])
    await view.ask(agent.peer_id, "first")
    await view.ask(agent.peer_id, "second")
    texts = [m.content for m in model.sent[-1]]
    assert texts == ["first", "coder: help me", "second"]
    await session.close()


async def test_other_peers_are_named():
    @connector("lab")
    @require(HookAsk)
    class Lab:
        ask : Ask

    model = fake(lambda messages: AIMessage(content="ok"))
    agent, lab = AgentConnector("agent", model), Lab()
    session, view = await driven(connectors=[agent, lab])
    await lab.ask(agent.peer_id, "results are in")
    await view.ask(agent.peer_id, "anything new?")
    assert [m.content for m in model.sent[-1]][:2] == ["lab: results are in", "ok"]
    await session.close()


async def test_one_thread_per_question():
    saver = InMemorySaver()
    agent = AgentConnector("agent", fake(says("ok")), checkpointer=saver)
    session, view = await driven(connectors=[agent])
    await view.ask(agent.peer_id, "one")
    await view.ask(agent.peer_id, "two")
    questions = [str(m.id) for m in view.context() if m.frm == LOCAL]
    threads = {c.config["configurable"]["thread_id"] for c in saver.list(None)}
    assert threads == set(questions) and len(threads) == 2
    await session.close()


# === The model may be an Endpoint ==================================================

async def test_created_without_the_key(monkeypatch):
    monkeypatch.delenv("AGENT_TEST_KEY", raising=False)
    agent = AgentConnector("agent", Endpoint(base_url="http://127.0.0.1:9/v1", api_key=Env("AGENT_TEST_KEY")))
    session, view = await driven(connectors=[agent])
    reply = await _asked(view, agent, "hi")
    assert reply.status == ReplyStatus.ERROR
    assert reply.text == "agent: AGENT_TEST_KEY is not set"
    await session.close()


async def test_the_key_is_read_when_the_model_is_called():
    reads: List[int] = []

    def secret() -> str:
        reads.append(1)
        return "sk-very-secret"

    agent = AgentConnector("agent", Endpoint(base_url="http://127.0.0.1:9/v1", model="m", api_key=secret))
    assert reads == [] and "sk-very-secret" not in repr(vars(agent))
    session, view = await driven(connectors=[agent])
    reply = await _asked(view, agent, "hi")          # nothing listens on port 9
    assert reads and reply.status == ReplyStatus.ERROR
    assert "sk-very-secret" not in reply.text
    await session.close()


async def test_an_endpoint_without_a_key():
    agent = AgentConnector("agent", Endpoint(base_url="http://127.0.0.1:9/v1"))
    session, view = await driven(connectors=[agent])
    reply = await _asked(view, agent, "hi")
    assert reply.text == "agent: the endpoint has no API key configured"
    await session.close()


def test_a_session_can_hold_it():
    assert isinstance(ChatSession(connectors=[AgentConnector("agent", fake(says("x")))]), ChatSession)
