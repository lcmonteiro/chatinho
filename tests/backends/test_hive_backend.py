"""
Tests for HiveBackend: a chat kept in a hive, over HTTP, with nothing to install.

They run against a real hive served on a free port (``fakes.hive``).
"""

import asyncio
import os
import subprocess
import sys
from typing import Callable, List

import httpx
import pytest

from chatinho import Attachment, HiveBackend, HookTrace, Trace, connector, require
from chatinho.support.parts.hive import KEY_HEADER, message_from_wire
from conftest import driven
from fakes.hive import make_hive, message, served, wire_messages


@connector("rastro")
@require(HookTrace)
class _Tracer:
    trace : Trace


async def until(check: Callable[[], bool], wait: float = 5.0) -> None:
    """Waits until *check* holds, failing the test after *wait* seconds."""
    deadline = asyncio.get_running_loop().time() + wait
    while not check():
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError("timed out waiting")
        await asyncio.sleep(0.05)


def admin_messages(hive, url: str, chat: str) -> List:
    answer = httpx.get("%s/api/chats/%s/messages" % (url, chat), headers={KEY_HEADER: hive.admin})
    return [message_from_wire(m) for m in answer.json()["messages"]]


def admin_traces(hive, url: str, chat: str, msg_id) -> List:
    answer = httpx.get("%s/api/chats/%s/messages/%s/traces" % (url, chat, msg_id),
                       headers={KEY_HEADER: hive.admin})
    return answer.json()["traces"]


@pytest.fixture
def hive(tmp_path):
    hive = make_hive(tmp_path, "team", "other")
    with served(hive.db) as server:
        hive.url = server.url                     # type: ignore[attr-defined]
        yield hive


# @ac AC-BACK-009.1
async def test_the_conversation_goes_to_the_hive_and_comes_back(hive):
    session, view = await driven(backend=HiveBackend(hive.url, hive.keys["team"]))
    first  = await view.say("one")
    second = await view.say("two", reply_to=first)
    await session.close()
    session, view = await driven(backend=HiveBackend(hive.url, hive.keys["team"]))
    got = list(view.context())
    await session.close()
    assert [(m.id, m.text, m.frm, m.to, m.reply_to, m.status) for m in got] == [
        (first, "one", 0, None, None, got[0].status),
        (second, "two", 0, None, first, got[1].status),
    ]


# @ac AC-BACK-009.1
async def test_the_hive_shows_the_speakers_name(hive):
    session, view = await driven(backend=HiveBackend(hive.url, hive.keys["team"]))
    await view.say("hello")
    await session.close()
    answer = httpx.get("%s/api/chats/team/messages" % hive.url, headers={KEY_HEADER: hive.admin})
    assert [m["frm_name"] for m in answer.json()["messages"]] == ["chat"]


# @ac AC-BACK-009.2
async def test_loading_narrows_by_count_and_time(hive):
    messages = [message(n) for n in range(1, 6)]
    httpx.post(hive.url + "/api/messages", json={"messages": wire_messages(*messages)},
               headers={KEY_HEADER: hive.keys["team"]})
    archive = HiveBackend(hive.url, hive.keys["team"])
    await archive.initialize()
    try:
        last_two   = await archive.load(limit=2)
        from_third = await archive.load(since=messages[2].timestamp)
    finally:
        await archive.shutdown()
    assert [m.id for m in last_two] == [m.id for m in messages[3:]]
    assert [m.id for m in from_third] == [m.id for m in messages[2:]]


# @ac AC-BACK-009.3
async def test_forgetting(hive):
    messages = [message(n) for n in range(1, 6)]
    httpx.post(hive.url + "/api/messages", json={"messages": wire_messages(*messages)},
               headers={KEY_HEADER: hive.keys["team"]})
    archive = HiveBackend(hive.url, hive.keys["team"])
    await archive.initialize()
    try:
        assert await archive.forget(before=messages[2].timestamp) == 2
        assert [m.id for m in await archive.load()] == [m.id for m in messages[2:]]
    finally:
        await archive.shutdown()


# @ac AC-BACK-009.4
async def test_traces_are_recorded_in_the_hive(hive):
    tracer        = _Tracer()
    session, view = await driven(connectors=[tracer], backend=HiveBackend(hive.url, hive.keys["team"]))
    msg_id = await view.say("summarise")
    first  = await tracer.trace(msg_id, "running", "extract")
    second = await tracer.trace(msg_id, "done", "extract", prev=first)
    await session.close()
    got = admin_traces(hive, hive.url, "team", msg_id)
    assert [(t["id"], t["state"], t["text"], t["prev"]) for t in got] == [
        (str(first), "running", "extract", None),
        (str(second), "done", "extract", str(first)),
    ]
    assert {t["frm_name"] for t in got} == {"rastro"}


# @ac AC-BACK-009.5
async def test_the_key_is_read_when_each_request_is_made(hive):
    current = [hive.keys["team"]]
    session, view = await driven(backend=HiveBackend(hive.url, lambda: current[0]))
    await view.say("for team")
    await until(lambda: [m.text for m in admin_messages(hive, hive.url, "team")] == ["for team"])
    current[0] = hive.keys["other"]
    await view.say("for other")
    await until(lambda: [m.text for m in admin_messages(hive, hive.url, "other")] == ["for other"])
    await session.close()
    assert [m.text for m in admin_messages(hive, hive.url, "team")] == ["for team"]


# @ac AC-BACK-009.6
def test_it_needs_no_extra():
    script = (
        "import builtins\n"
        "real = builtins.__import__\n"
        "def blocked(name, *a, **k):\n"
        "    if name.split('.')[0] in ('fastapi', 'uvicorn', 'sqlalchemy', 'httpx', 'starlette'):\n"
        "        raise ImportError(name)\n"
        "    return real(name, *a, **k)\n"
        "builtins.__import__ = blocked\n"
        "from chatinho import HiveBackend\n"
        "from chatinho.backends.hive import HiveBackend as Same\n"
        "assert HiveBackend is Same\n"
        "print('ok')\n"
    )
    done = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "ok"


def notes() -> Attachment:
    return Attachment(name="notes.md", media_type="text/markdown", data="# notas\n\nolá".encode())


def attachment_in_hive(hive, msg_id) -> bool:
    answer = httpx.get("%s/api/messages/%s/attachments/notes.md" % (hive.url, msg_id),
                       headers={KEY_HEADER: hive.keys["team"]})
    return answer.status_code == 200


# @ac AC-BACK-010.1
async def test_an_attachment_comes_back_as_a_local_file(hive):
    archive       = HiveBackend(hive.url, hive.keys["team"])
    session, view = await driven(backend=archive)
    msg_id = await view.say("see [notes](notes.md)", attachments=[notes()])
    await until(lambda: attachment_in_hive(hive, msg_id))
    path = await archive.link(msg_id, "notes.md")
    try:
        assert path is not None
        with open(path, "rb") as f:
            assert f.read() == notes().data
    finally:
        await session.close()


# @ac AC-BACK-010.2
async def test_nothing_by_that_name_is_none(hive):
    archive       = HiveBackend(hive.url, hive.keys["team"])
    session, view = await driven(backend=archive)
    msg_id = await view.say("no attachments")
    try:
        assert await archive.link(msg_id, "missing.md") is None
    finally:
        await session.close()


# @ac AC-BACK-010.3
async def test_linked_files_go_at_shutdown(hive):
    archive       = HiveBackend(hive.url, hive.keys["team"])
    session, view = await driven(backend=archive)
    msg_id = await view.say("see [notes](notes.md)", attachments=[notes()])
    await until(lambda: attachment_in_hive(hive, msg_id))
    path = await archive.link(msg_id, "notes.md")
    assert path is not None and os.path.exists(path)
    await session.close()
    assert not os.path.exists(path)
