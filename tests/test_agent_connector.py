"""
AgentConnector: a LangChain agent as a peer, with the chat as its tools.

Every agent here runs on a scripted model (``fakes.agent``), so no key and no
network: the script decides each call from the messages of that run alone.
"""

import asyncio
import json
from typing import Any, Dict, List, Optional

import pytest
from langchain.agents.structured_output import ToolStrategy
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
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
    HookKeep,
    HookSay,
    LOCAL,
    Reply,
    ReplyStatus,
    Say,
    backend,
    connector,
    require,
)
from chatinho.connectors import agent as module
from chatinho.connectors.agent import AgentConnector
from chatinho.keys import Env

from fakes.agent import File, calls, fake, maker, makes, question, reminders, says
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
    assert (await view.ask(agent.peer_id, "hello")).text == "Hi."
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
    assert (await view.ask(agent.peer_id, "Weather?")).text == "It is sunny in Porto."
    await session.close()


async def test_text_blocks_are_joined():
    blocks = [{"type": "text", "text": "Hello, "}, {"type": "text", "text": "Ana."}]
    agent = AgentConnector("agent", fake(lambda messages: AIMessage(content=blocks)))
    session, view = await driven(connectors=[agent])
    assert (await view.ask(agent.peer_id, "hi")).text == "Hello, Ana."
    await session.close()


async def test_a_structured_answer():
    class Forecast(BaseModel):
        city : str
        sky  : str

    model = fake(calls("Forecast", city="Porto", sky="sunny"))
    agent = AgentConnector("agent", model, response_format=ToolStrategy(Forecast))
    session, view = await driven(connectors=[agent])
    assert json.loads((await view.ask(agent.peer_id, "Weather?")).text) == {"city": "Porto", "sky": "sunny"}
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
    assert sorted(a.text for a in answers) == ["re: one", "re: two"]
    await session.close()


# === The graph =====================================================================

async def test_the_graph_has_the_four_steps():
    agent = AgentConnector("agent", fake(says("x")))
    session, view = await driven(connectors=[agent])
    graph = (await agent.graph()).get_graph()
    assert set(graph.nodes) == {"__start__", "extract", "agent", "verify", "load", "__end__"}
    assert {(e.source, e.target) for e in graph.edges} == {
        ("__start__", "extract"), ("extract", "agent"), ("agent", "verify"),
        ("verify", "agent"), ("verify", "load"), ("load", "__end__"),
    }
    await session.close()


# === Files the agent made are attached =============================================

@backend("keeper")
@require(HookKeep)
class _Keeper:
    """Keeps what is attached, by message id: the names only."""

    def __init__(self) -> None:
        self.kept : Dict[Any, List[str]] = {}

    async def keep(self, msg_id: Any, attachments: Any) -> None:
        self.kept[msg_id] = [a.name for a in attachments]

    async def link(self, msg_id: Any, name: str) -> Optional[str]:
        return None


async def _responses(view, agent, count: int) -> List[ChatMessage]:
    """Waits until the agent has said *count* messages, and returns them."""
    for _ in range(200):
        said = [m for m in view.context() if m.frm == agent.peer_id]
        if len(said) >= count:
            return said
        await asyncio.sleep(0.01)
    raise AssertionError("the agent said %d of %d messages" % (len(said), count))


async def test_a_tool_makes_a_diagram():
    model = fake(makes("flow.svg", answers=["Here: [Flow](flow.svg)"]))
    agent = AgentConnector("agent", model, tools=[maker()])
    session, view = await driven(connectors=[agent])
    reply = await agent.answer(ChatMessage(id="q-1", text="Draw the flow", frm=LOCAL, to=1))
    assert reply.text == "Here: [Flow](flow.svg)"
    (made,) = reply.attachments
    assert (made.name, made.media_type, made.data) == ("flow.svg", "image/svg+xml", b"<svg/>")
    await session.close()


async def test_an_attachment_is_kept_as_it_is():
    from chatinho import Attachment
    from langchain_core.tools import StructuredTool

    file = Attachment(name="raw.bin", media_type="application/octet-stream", data=b"\x00\x01")
    tool = StructuredTool.from_function(lambda name: ("made", file), name="make_file",
                                        description="Make a file.", response_format="content_and_artifact")
    agent = AgentConnector("agent", fake(makes("raw.bin", answers=["[raw](raw.bin)"])), tools=[tool])
    session, view = await driven(connectors=[agent])
    reply = await agent.answer(ChatMessage(id="q-1", text="go", frm=LOCAL, to=1))
    assert reply.attachments == (file,)
    await session.close()


async def test_a_plain_answer_has_no_attachments():
    agent = AgentConnector("agent", fake(says("just text")), tools=[maker()])
    session, view = await driven(connectors=[agent])
    reply = await agent.answer(ChatMessage(id="q-1", text="hi", frm=LOCAL, to=1))
    assert (reply.text, reply.attachments) == ("just text", ())
    await session.close()


async def test_only_this_runs_files():
    def script(messages):
        if question(messages) == "draw":
            return makes("flow.svg", answers=["[Flow](flow.svg)"])(messages)
        return AIMessage(content="nothing new")

    agent = AgentConnector("agent", fake(script), tools=[maker()])
    session, view = await driven(connectors=[agent])
    await view.ask(agent.peer_id, "draw")
    reply = await agent.answer(ChatMessage(id="q-2", text="and now?", frm=LOCAL, to=1))
    assert (reply.text, reply.attachments) == ("nothing new", ())
    await session.close()


async def test_the_last_file_of_a_name_is_kept():
    first, second = File("a.svg", "image/svg+xml", "<one/>"), File("a.svg", "image/svg+xml", "<two/>")
    files = iter([first, second])
    from langchain_core.tools import StructuredTool
    tool = StructuredTool.from_function(lambda name: ("made", next(files)), name="make_file",
                                        description="Make a file.", response_format="content_and_artifact")
    agent = AgentConnector("agent", fake(makes("a.svg", "a.svg", answers=["[A](a.svg)"])), tools=[tool])
    session, view = await driven(connectors=[agent])
    reply = await agent.answer(ChatMessage(id="q-1", text="go", frm=LOCAL, to=1))
    assert [(a.name, a.data) for a in reply.attachments] == [("a.svg", b"<two/>")]
    await session.close()


async def test_the_files_reach_the_backend():
    keeper = _Keeper()
    agent  = AgentConnector("agent", fake(makes("flow.svg", answers=["[Flow](flow.svg)"])), tools=[maker()])
    session, view = await driven(connectors=[agent], backend=keeper)
    assert (await view.ask(agent.peer_id, "draw")).text == "[Flow](flow.svg)"
    reply = next(m for m in view.context() if m.frm == agent.peer_id)
    assert keeper.kept[reply.id] == ["flow.svg"]
    await session.close()


# === The answer links its files ====================================================

async def test_a_missing_link_is_asked_for():
    model = fake(makes("report.svg", answers=["Ready.", "Here: [Report](report.svg)."]))
    agent = AgentConnector("agent", model, tools=[maker()])
    session, view = await driven(connectors=[agent])
    reply = await agent.answer(ChatMessage(id="q-1", text="report?", frm=LOCAL, to=1))
    assert len(model.sent) == 3
    (reminder,) = reminders(model.sent[2])
    assert isinstance(model.sent[2][-1], HumanMessage) and "(report.svg)" in reminder
    assert reply.text == "Here: [Report](report.svg)."
    assert [a.name for a in reply.attachments] == ["report.svg"]
    await session.close()


async def test_sent_back_at_most_link_retries_times():
    model = fake(makes("report.svg", answers=["Ready.", "Still ready."]))
    agent = AgentConnector("agent", model, tools=[maker()])
    session, view = await driven(connectors=[agent])
    reply = await agent.answer(ChatMessage(id="q-1", text="report?", frm=LOCAL, to=1))
    assert len(model.sent) == 3
    assert reply.text == "Still ready." and [a.name for a in reply.attachments] == ["report.svg"]
    await session.close()


async def test_more_retries_when_asked_for():
    model = fake(makes("report.svg", answers=["Ready.", "Still ready.", "[Report](report.svg)"]))
    agent = AgentConnector("agent", model, tools=[maker()], link_retries=2)
    session, view = await driven(connectors=[agent])
    reply = await agent.answer(ChatMessage(id="q-1", text="report?", frm=LOCAL, to=1))
    assert len(model.sent) == 4 and reply.text == "[Report](report.svg)"
    await session.close()


async def test_verify_turned_off():
    model = fake(makes("report.svg", answers=["Ready.", "never"]))
    agent = AgentConnector("agent", model, tools=[maker()], link_retries=0)
    session, view = await driven(connectors=[agent])
    reply = await agent.answer(ChatMessage(id="q-1", text="report?", frm=LOCAL, to=1))
    assert len(model.sent) == 2
    assert reply.text == "Ready." and [a.name for a in reply.attachments] == ["report.svg"]
    await session.close()


async def test_linked_the_first_time():
    model = fake(makes("flow.svg", answers=["Here: [Flow](flow.svg)"]))
    agent = AgentConnector("agent", model, tools=[maker()])
    session, view = await driven(connectors=[agent])
    await agent.answer(ChatMessage(id="q-1", text="draw", frm=LOCAL, to=1))
    assert len(model.sent) == 2 and not any(reminders(sent) for sent in model.sent)
    await session.close()


# === The user's says are responded to with a say ===================================

async def test_the_user_says_something_to_everyone():
    keeper = _Keeper()
    model  = fake(makes("login.svg", answers=["Here: [Login](login.svg)"]))
    agent  = AgentConnector("agent", model, tools=[maker()])
    # Two peers answer, so what the user says stays a say to everyone.
    session, view = await driven(connectors=[agent, _Echo("coder")], backend=keeper)
    said = await view.say("Draw the login flow")
    await session.close()
    (response,) = [m for m in view.context() if m.frm == agent.peer_id]
    assert (response.text, response.to, response.reply_to) == ("Here: [Login](login.svg)", None, said)
    assert keeper.kept[response.id] == ["login.svg"]


async def test_another_peer_says_something_to_everyone():
    @connector("lab")
    @require(HookSay)
    class Lab:
        say : Say

    model = fake(says("never"))
    agent, lab = AgentConnector("agent", model), Lab()
    session, view = await driven(connectors=[agent, _Echo("coder"), lab])
    await lab.say("hello")
    await session.close()
    assert model.sent == []
    assert not [m for m in view.context() if m.frm == agent.peer_id]


async def test_asked_directly():
    model = fake(says("once"))
    agent = AgentConnector("agent", model)
    session, view = await driven(connectors=[agent, _Echo("coder")])
    assert (await view.ask(agent.peer_id, "hi")).text == "once"
    await session.close()
    assert len(model.sent) == 1
    assert [m.text for m in view.context() if m.frm == agent.peer_id] == ["once"]


async def test_the_only_answering_peer_answers_once():
    """Alone, the agent is asked the user's say, which is still a broadcast: one run, one reply."""
    model = fake(says("once"))
    agent = AgentConnector("agent", model)
    session, view = await driven(connectors=[agent])
    said = await view.say("hi")
    await session.close()
    assert len(model.sent) == 1
    mine = [m for m in view.context() if m.frm == agent.peer_id]
    assert [(m.text, m.reply_to, m.to) for m in mine] == [("once", said, None)]


async def test_the_run_fails_on_a_say():
    model = fake(says("never"))
    model.error = RuntimeError("the prompt was secret")
    agent = AgentConnector("agent", model)
    session, view = await driven(connectors=[agent, _Echo("coder")])
    said = await view.say("hi")
    await session.close()
    (response,) = [m for m in view.context() if m.frm == agent.peer_id]
    assert (response.text, response.reply_to) == ("agent: could not answer (RuntimeError)", said)


# === The chat as tools =============================================================

async def test_asking_another_peer():
    model = fake(calls("ask_coder", question="Write a test"))
    agent = AgentConnector("agent", model)
    session, view = await driven(connectors=[agent, _Echo("coder")])
    # The tool hands the model the Reply itself, which reads as its text.
    assert (await view.ask(agent.peer_id, "go")).text == "coder: Write a test"
    asked = [m for m in view.context() if m.frm == agent.peer_id and m.reply_to is None]
    assert [m.text for m in asked] == ["Write a test"]
    await session.close()


async def test_running_a_command():
    model = fake(calls("run_help"))
    agent = AgentConnector("agent", model)
    session, view = await driven(connectors=[agent], commands=[HelpCommand()])
    assert "/help" in (await view.ask(agent.peer_id, "what can you do?")).text
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
    assert (await view.ask(agent.peer_id, "Weather?")).text == "In %s" % Reply("Porto")
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
    assert (await view.ask(agent.peer_id, "go")).text == "mine"
    assert model.tools[-1] == ["ask_coder"]
    assert "hides the chat's" in caplog.text
    await session.close()


@connector("quota")
@require(HookAnswer)
class _OutOfQuota:
    async def answer(self, msg: ChatMessage) -> Reply:
        return Reply("quota exceeded", status=ReplyStatus.ERROR)


async def test_a_peers_error_reply_reaches_the_model_as_a_failure():
    """An error reply is the peer's own words, so the model is told them, as a failure."""
    model = fake(calls("ask_quota", question="x", then=lambda result: "It said: " + result))
    agent = AgentConnector("agent", model)
    session, view = await driven(connectors=[agent, _OutOfQuota()])
    assert (await view.ask(agent.peer_id, "go")).text == "It said: error: quota exceeded"
    await session.close()


def _tool_results(model: Any) -> List[str]:
    """What the model was handed as tool results in its last call."""
    return [str(m.content) for m in model.sent[-1] if isinstance(m, ToolMessage)]


async def test_the_model_reads_an_answer_as_its_text():
    model = fake(calls("ask_coder", question="Write a test"))
    agent = AgentConnector("agent", model)
    session, view = await driven(connectors=[agent, _Echo("coder")])
    await view.ask(agent.peer_id, "go")
    assert _tool_results(model) == ["coder: Write a test"]
    await session.close()


async def test_the_model_reads_an_error_reply_as_one():
    model = fake(calls("ask_quota", question="x"))
    agent = AgentConnector("agent", model)
    session, view = await driven(connectors=[agent, _OutOfQuota()])
    await view.ask(agent.peer_id, "go")
    assert _tool_results(model) == ["error: quota exceeded"]
    await session.close()


async def test_a_failing_peer():
    model = fake(calls("ask_broken", question="x", then=lambda result: "It said: " + result))
    agent = AgentConnector("agent", model)
    session, view = await driven(connectors=[agent, _Broken()])
    assert (await view.ask(agent.peer_id, "go")).text == "It said: error: broken failed: RuntimeError"
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
            return Reply("coder<%s>" % (await self.ask(1, "and you?")).text)

    def script(messages):
        if question(messages) == "and you?":
            return AIMessage(content="agent again")
        return calls("ask_coder", question="what do you think?")(messages)

    agent = AgentConnector("agent", fake(script))
    session, view = await driven(connectors=[agent, Coder()])
    assert agent.peer_id == 1
    answer = await asyncio.wait_for(view.ask(agent.peer_id, "go"), timeout=5)
    assert answer.text == "coder<agent again>"
    await session.close()


async def test_a_loop_of_agents_stops_at_max_depth():
    ping = AgentConnector("ping", fake(calls("ask_pong", question="again")), peers=["pong"])
    pong = AgentConnector("pong", fake(calls("ask_ping", question="again")), peers=["ping"])
    session, view = await driven(connectors=[ping, pong], max_depth=4)
    answer = await asyncio.wait_for(view.ask(ping.peer_id, "go"), timeout=5)
    # The innermost tool got the limit's ERROR reply; each agent above echoes what its tool read.
    assert answer.text == "error: too many nested asks (limit 4)"
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


async def test_it_remembers_what_the_user_said_to_everyone():
    model = fake(lambda messages: AIMessage(content="noted: " + question(messages)))
    agent = AgentConnector("agent", model)
    session, view = await driven(connectors=[agent, _Echo("coder")])
    await view.say("My name is Ana")
    await _responses(view, agent, 1)
    await view.say("What is my name?")
    await _responses(view, agent, 2)
    await session.close()
    second = model.sent[-1]
    assert [type(m) for m in second] == [HumanMessage, AIMessage, HumanMessage]
    assert [m.content for m in second] == ["My name is Ana", "noted: My name is Ana", "What is my name?"]


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
