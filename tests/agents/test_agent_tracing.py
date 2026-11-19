"""
AgentPeer traces its runs: the graph's nodes, the model calls and the tool calls, as a graph.

The model is scripted (``fakes.agent``) and the recorder keeps every trace.
"""

import asyncio
import itertools
from typing import Any, Dict, FrozenSet, List

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.tools import tool

from chatinho import ChatTrace, HookRecord, TraceState, backend, require
from chatinho.support.kits.agent import AgentPeer
from conftest import driven
from fakes.agent import calls, fake, says, this_run

NODES = ("extract", "agent", "verify", "load")
_ids  = itertools.count(1)


class _Factory:
    name    : str            = "plain"
    options : FrozenSet[str] = frozenset({"name", "system_prompt"})
    covered : FrozenSet[str] = frozenset()

    async def build(self, model: Any, tools: List[Any], options: Dict[str, Any], peer: Any) -> Any:
        return create_agent(model, tools=tools, **options)


@backend("registo")
@require(HookRecord)
class _Recorder:
    def __init__(self) -> None:
        self.traces : List[ChatTrace] = []

    async def record(self, trace: ChatTrace) -> None:
        self.traces.append(trace)

    def of(self, msg_id) -> List[ChatTrace]:
        return [t for t in self.traces if t.msg_id == msg_id]


@backend("partido")
@require(HookRecord)
class _Broken:
    async def record(self, trace: ChatTrace) -> None:
        raise RuntimeError("disk full")


@tool
def ws_ls(path: str) -> str:
    """Lists a folder."""
    return "README.md\nsrc"


@tool
def ws_read(path: str) -> str:
    """Reads a file."""
    return "# chatinho"


@tool
def explode(path: str) -> str:
    """Always fails."""
    raise RuntimeError("boom")


def two_at_once(messages: List[BaseMessage]) -> AIMessage:
    """Calls ws_ls and ws_read in one turn, then answers."""
    if not [m for m in this_run(messages) if isinstance(m, ToolMessage)]:
        return AIMessage(content="", tool_calls=[
            {"name": "ws_ls", "args": {"path": "."}, "id": "call-%d" % next(_ids)},
            {"name": "ws_read", "args": {"path": "README.md"}, "id": "call-%d" % next(_ids)},
        ])
    return AIMessage(content="two things")


async def asked(script, tools=(), recorder=None, questions=("summarise the repo",)):
    recorder = recorder if recorder is not None else _Recorder()
    peer     = AgentPeer("dev", fake(script), _Factory(), tools=list(tools))
    session, view = await driven(connectors=[peer], backend=recorder)
    replies  = await asyncio.gather(*(view.ask(peer.peer_id, q) for q in questions))
    ids      = [m.id for m in view.context() if m.text in questions]
    await session.close()
    return recorder, replies, ids


def by_id(traces: List[ChatTrace]) -> Dict[Any, ChatTrace]:
    return {t.id: t for t in traces}


def starts(traces: List[ChatTrace], prefix: str) -> List[ChatTrace]:
    return [t for t in traces if t.state is TraceState.RUNNING and t.text.startswith(prefix)]


def end_of(traces: List[ChatTrace], start: ChatTrace) -> ChatTrace:
    return next(t for t in traces if t.prev == start.id and t.state is not TraceState.RUNNING
                and t.text.split()[0] == start.text.split()[0])


# @ac AC-AGENT-012.1
async def test_the_nodes_of_a_run():
    recorder, replies, [msg_id] = await asked(says("It is a chat library."))
    assert replies[0].text == "It is a chat library."
    traces = recorder.of(msg_id)
    assert traces and all(t.msg_id == msg_id for t in traces)
    for node in NODES:
        started = [t for t in traces if t.state is TraceState.RUNNING and t.text == node]
        assert len(started) == 1, node
        ended = [t for t in traces
                 if t.state is TraceState.DONE and t.text.startswith(node) and t.prev == started[0].id]
        assert len(ended) == 1, node


# @ac AC-AGENT-012.1
async def test_every_prev_is_a_trace_of_the_same_run():
    recorder, _, [msg_id] = await asked(says("ok"))
    traces = recorder.of(msg_id)
    known  = by_id(traces)
    assert sum(1 for t in traces if t.prev is None) == 1
    assert all(t.prev is None or t.prev in known for t in traces)


# @ac AC-AGENT-012.2
async def test_a_tool_call_follows_the_model_call_that_asked_for_it():
    recorder, _, [msg_id] = await asked(calls("ws_ls", path="."), tools=[ws_ls])
    traces = recorder.of(msg_id)
    known  = by_id(traces)
    [tool_start] = starts(traces, "tool ws_ls")
    assert "." in tool_start.text
    before = known[tool_start.prev]
    assert before.text.startswith("model") and before.state is TraceState.DONE
    tool_end = end_of(traces, tool_start)
    assert tool_end.state is TraceState.DONE
    assert "README.md" in tool_end.text


# @ac AC-AGENT-012.3
async def test_two_tool_calls_at_once_follow_the_same_trace():
    recorder, replies, [msg_id] = await asked(two_at_once, tools=[ws_ls, ws_read])
    assert replies[0].text == "two things"
    traces = recorder.of(msg_id)
    [ls] = starts(traces, "tool ws_ls")
    [rd] = starts(traces, "tool ws_read")
    assert ls.prev == rd.prev and ls.prev is not None


# @ac AC-AGENT-012.4
async def test_a_tool_that_fails_ends_in_error():
    recorder, _, [msg_id] = await asked(calls("explode", path="."), tools=[explode])
    traces = recorder.of(msg_id)
    [start] = starts(traces, "tool explode")
    end = end_of(traces, start)
    assert end.state is TraceState.ERROR
    assert "RuntimeError" in end.text


# @ac AC-AGENT-012.5
async def test_tracing_never_fails_the_run():
    _, replies, _ = await asked(says("still answers"), recorder=_Broken())
    assert replies[0].text == "still answers"
    assert str(replies[0]) == "still answers"


# @ac AC-AGENT-012.6
async def test_each_question_is_its_own_graph():
    recorder, _, ids = await asked(says("ok"), questions=("one", "two"))
    assert len(ids) == 2
    for msg_id in ids:
        traces = recorder.of(msg_id)
        mine   = {t.id for t in traces}
        assert traces
        assert all(t.prev is None or t.prev in mine for t in traces)
