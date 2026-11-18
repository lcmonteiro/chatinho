"""
Tests for traces: the steps of processing a message, recorded beside the conversation.

A peer that declares ``HookTrace`` is granted ``trace``; the session makes the
trace, hands it to whoever declared ``HookRecord``, and keeps it out of the
conversation entirely.
"""

import logging
import subprocess
import sys
from typing import List

import pytest

from chatinho import (
    TOOL,
    TRACE_TEXT_LIMIT,
    ChatMessage,
    ChatTrace,
    HookExecute,
    HookListen,
    HookRecord,
    HookTrace,
    MessageID,
    Reply,
    Trace,
    TraceID,
    TraceState,
    backend,
    connector,
    require,
    tool,
)
from conftest import driven


@backend("registo")
@require(HookRecord)
class _Recorder:
    def __init__(self) -> None:
        self.traces : List[ChatTrace] = []

    async def record(self, trace: ChatTrace) -> None:
        self.traces.append(trace)


@backend("registo-ouvinte")
@require(HookRecord)
@require(HookListen)
class _ListeningRecorder(_Recorder):
    def __init__(self) -> None:
        super().__init__()
        self.heard : List[ChatMessage] = []

    async def listen(self, msg: ChatMessage) -> None:
        self.heard.append(msg)


@backend("partido")
@require(HookRecord)
class _BrokenRecorder:
    async def record(self, trace: ChatTrace) -> None:
        raise RuntimeError("disk full")


@connector("rastro")
@require(HookTrace)
class _Tracer:
    trace : Trace


@connector("ouvido")
@require(HookListen)
class _Ear:
    def __init__(self) -> None:
        self.heard : List[object] = []

    async def listen(self, msg: ChatMessage) -> None:
        self.heard.append(msg)


@tool("passos", "Traces a step while it runs")
@require(HookExecute)
@require(HookTrace)
class _TracingCommand:
    trace : Trace

    def __init__(self, msg_id: MessageID) -> None:
        self.msg_id = msg_id

    async def execute(self, args: str = "", **kwargs) -> Reply:
        await self.trace(self.msg_id, "done", "ran")
        return Reply("ok")


# @ac AC-CORE-030.1
async def test_a_trace_is_recorded_with_everything_it_holds():
    recorder, tracer = _Recorder(), _Tracer()
    session, view    = await driven(connectors=[tracer], backend=recorder)
    msg_id   = await view.say("summarise the repo")
    trace_id = await tracer.trace(msg_id, TraceState.RUNNING, "extract")
    await session.close()
    assert isinstance(trace_id, TraceID)
    [trace] = recorder.traces
    assert trace.id == trace_id
    assert trace.msg_id == msg_id
    assert trace.state is TraceState.RUNNING
    assert trace.text == "extract"
    assert trace.prev is None
    assert trace.frm == session.id_of(tracer)
    assert trace.timestamp is not None


# @ac AC-CORE-030.1
async def test_a_trace_id_reads_back_as_itself():
    recorder, tracer = _Recorder(), _Tracer()
    session, view    = await driven(connectors=[tracer], backend=recorder)
    trace_id = await tracer.trace(await view.say("hi"), "running", "step")
    await session.close()
    assert str(trace_id).startswith("trc-") and len(str(trace_id)) == len("trc-") + 16
    assert TraceID.parse(str(trace_id)) == trace_id


# @ac AC-CORE-030.2
async def test_one_trace_follows_another():
    recorder, tracer = _Recorder(), _Tracer()
    session, view    = await driven(connectors=[tracer], backend=recorder)
    msg_id = await view.say("hi")
    first  = await tracer.trace(msg_id, "running", "agent")
    second = await tracer.trace(msg_id, "done", "agent", prev=first)
    await session.close()
    assert [t.id for t in recorder.traces] == [first, second]
    assert recorder.traces[1].prev == first


# @ac AC-CORE-030.3
async def test_the_state_by_its_name():
    recorder, tracer = _Recorder(), _Tracer()
    session, view    = await driven(connectors=[tracer], backend=recorder)
    await tracer.trace(await view.say("hi"), "done", "load")
    await session.close()
    assert recorder.traces[0].state is TraceState.DONE


# @ac AC-CORE-030.4
async def test_an_unknown_state_is_refused():
    recorder, tracer = _Recorder(), _Tracer()
    session, view    = await driven(connectors=[tracer], backend=recorder)
    msg_id = await view.say("hi")
    with pytest.raises(ValueError, match="running.*done.*error|running"):
        await tracer.trace(msg_id, "finished", "load")
    await session.close()
    assert recorder.traces == []


# @ac AC-CORE-030.5
async def test_a_long_text_is_cut():
    recorder, tracer = _Recorder(), _Tracer()
    session, view    = await driven(connectors=[tracer], backend=recorder)
    await tracer.trace(await view.say("hi"), "done", "x" * 5000)
    await session.close()
    text = recorder.traces[0].text
    assert len(text) == TRACE_TEXT_LIMIT
    assert text.endswith("…")


# @ac AC-CORE-030.5
async def test_a_text_at_the_limit_is_kept_whole():
    recorder, tracer = _Recorder(), _Tracer()
    session, view    = await driven(connectors=[tracer], backend=recorder)
    await tracer.trace(await view.say("hi"), "done", "x" * TRACE_TEXT_LIMIT)
    await session.close()
    assert recorder.traces[0].text == "x" * TRACE_TEXT_LIMIT


# @ac AC-CORE-030.6
async def test_a_command_traces_as_tool():
    recorder      = _Recorder()
    session, view = await driven(backend=recorder)
    msg_id        = await view.say("hi")
    session.add_command(_TracingCommand(msg_id))
    await view.command("passos")
    await session.close()
    assert [t.frm for t in recorder.traces] == [TOOL]


# @ac AC-CORE-030.7
async def test_a_plain_string_is_not_a_message_id():
    recorder, tracer = _Recorder(), _Tracer()
    session, view    = await driven(connectors=[tracer], backend=recorder)
    msg_id = await view.say("hi")
    with pytest.raises(TypeError):
        await tracer.trace(str(msg_id), "running", "extract")  # type: ignore[arg-type]
    await session.close()
    assert recorder.traces == []


# @ac AC-CORE-031.1
async def test_a_prev_the_session_never_made_is_refused():
    recorder, tracer = _Recorder(), _Tracer()
    session, view    = await driven(connectors=[tracer], backend=recorder)
    msg_id = await view.say("hi")
    with pytest.raises(ValueError):
        await tracer.trace(msg_id, "done", "load", prev=TraceID.new())
    await session.close()
    assert recorder.traces == []


# @ac AC-CORE-031.2
async def test_another_peers_trace_may_be_followed():
    recorder = _Recorder()
    a, b     = _Tracer(), _Tracer()
    b.name   = "outro"
    session, view = await driven(connectors=[a, b], backend=recorder)
    msg_id = await view.say("hi")
    first  = await a.trace(msg_id, "running", "ask")
    await b.trace(msg_id, "running", "answer", prev=first)
    await session.close()
    assert recorder.traces[1].prev == first
    assert recorder.traces[1].frm == session.id_of(b)


# @ac AC-CORE-032.1
async def test_with_no_recorder_a_trace_still_gets_an_id():
    tracer        = _Tracer()
    session, view = await driven(connectors=[tracer])
    trace_id = await tracer.trace(await view.say("hi"), "running", "extract")
    await session.close()
    assert isinstance(trace_id, TraceID)


# @ac AC-CORE-032.2
async def test_a_recorder_that_raises_is_logged(caplog):
    tracer        = _Tracer()
    session, view = await driven(connectors=[tracer], backend=_BrokenRecorder())
    msg_id = await view.say("hi")
    with caplog.at_level(logging.ERROR):
        trace_id = await tracer.trace(msg_id, "running", "extract")
    await session.close()
    assert isinstance(trace_id, TraceID)
    assert any(r.levelno >= logging.ERROR for r in caplog.records)


# @ac AC-CORE-032.3
async def test_a_trace_is_not_heard_and_not_in_the_conversation():
    recorder, tracer, ear = _Recorder(), _Tracer(), _Ear()
    session, view = await driven(connectors=[tracer, ear], backend=recorder)
    msg_id = await view.say("hi")
    before = list(view.context())
    await tracer.trace(msg_id, "running", "extract")
    await tracer.trace(msg_id, "done", "extract")
    after = list(view.context())
    await session.close()
    assert after == before
    assert all(isinstance(m, ChatMessage) for m in ear.heard)
    assert [m.text for m in ear.heard] == ["hi"]


# @ac AC-CORE-032.4
async def test_a_recorder_that_listens_gets_traces_only_through_record():
    recorder, tracer = _ListeningRecorder(), _Tracer()
    session, view    = await driven(connectors=[tracer], backend=recorder)
    msg_id = await view.say("hi")
    await tracer.trace(msg_id, "running", "extract")
    await session.close()
    assert [m.text for m in recorder.heard] == ["hi"]
    assert len(recorder.traces) == 1


# @ac AC-CORE-033.1
def test_the_trace_names_need_no_extra():
    blocked = ("textual", "openai", "sqlalchemy", "mcp", "fastmcp", "fastapi", "uvicorn", "langchain",
               "langchain_core", "httpx")
    script = (
        "import builtins\n"
        "real = builtins.__import__\n"
        "def blocked(name, *a, **k):\n"
        "    if name.split('.')[0] in %r:\n"
        "        raise ImportError(name)\n"
        "    return real(name, *a, **k)\n"
        "builtins.__import__ = blocked\n"
        "import chatinho\n"
        "for n in ('ChatTrace', 'TraceID', 'TraceState', 'TRACE_TEXT_LIMIT', 'HookTrace', 'HookRecord',"
        " 'Trace'):\n"
        "    getattr(chatinho, n)\n"
        "print('ok')\n" % (blocked,)
    )
    done = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "ok"


# @ac AC-CORE-033.1
def test_the_hooks_grant_and_demand_one_thing_each():
    assert HookTrace.grants == ("trace",) and HookTrace.method is None
    assert HookRecord.method == "record" and HookRecord.grants == ()


# @ac AC-CORE-033.2
def test_a_recorder_without_record_is_refused():
    with pytest.raises(TypeError, match="record"):
        @require(HookRecord)
        class _NoRecord:
            pass
