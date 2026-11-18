"""
Tests for HiveBackend when the hive is slow, down, or refuses the key: the chat goes on.
"""

import asyncio
import logging
import socket
import time

import pytest

from chatinho import HiveBackend, HiveUnavailable, HookTrace, Trace, connector, require
from conftest import driven
from fakes.hive import down_url, free_port, make_hive, message, served


@connector("rastro")
@require(HookTrace)
class _Tracer:
    trace : Trace


@pytest.fixture
def silent_url():
    """An address that accepts connections and never answers: a hive that hangs."""
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen(16)
    yield "http://127.0.0.1:%d" % sock.getsockname()[1]
    sock.close()


async def eventually(check, wait: float = 10.0) -> None:
    deadline = time.monotonic() + wait
    while not check():
        if time.monotonic() > deadline:
            raise AssertionError("timed out waiting")
        await asyncio.sleep(0.1)


# @ac AC-BACK-011.1
async def test_saying_does_not_wait_on_a_hive_that_hangs(tmp_path, silent_url):
    archive       = HiveBackend(silent_url, "hive_x", timeout=2.0, flush_timeout=0.2)
    session, view = await driven(backend=archive)
    msg     = message(1)
    started = time.monotonic()
    await archive.listen(msg)
    took = time.monotonic() - started
    await view.say("and this")
    await session.close()
    assert took < 0.5


# @ac AC-BACK-011.2
async def test_what_waited_is_sent_in_order_once_the_hive_is_up(tmp_path):
    import httpx
    import json

    hive    = make_hive(tmp_path, "team")
    port    = free_port()
    url     = "http://127.0.0.1:%d" % port
    tracer  = _Tracer()
    session, view = await driven(connectors=[tracer], backend=HiveBackend(url, hive.keys["team"]))
    one   = await view.say("one")
    two   = await view.say("two")
    three = await view.say("three")
    step  = await tracer.trace(one, "running", "extract")
    got   = []
    with served(hive.db, port=port):
        async with httpx.AsyncClient() as client:
            async with client.stream("GET", url + "/api/chats/team/stream", params={"key": hive.admin},
                                     timeout=None) as stream:
                async def read():
                    async for line in stream.aiter_lines():
                        if line.startswith("data:"):
                            got.append(json.loads(line[5:])["id"])
                            if len(got) == 4:
                                return
                await asyncio.wait_for(read(), 30)
        await session.close()
    assert got == [str(one), str(two), str(three), str(step)]


# @ac AC-BACK-011.3
async def test_a_full_queue_drops_the_oldest_and_says_so(tmp_path, caplog):
    hive    = make_hive(tmp_path, "team")
    port    = free_port()
    url     = "http://127.0.0.1:%d" % port
    archive = HiveBackend(url, hive.keys["team"], queue_limit=2)
    with caplog.at_level(logging.WARNING):
        session, view = await driven(backend=archive)
        await view.say("one")
        await view.say("two")
        await view.say("three")
    assert any("dropped" in r.getMessage() and "1" in r.getMessage() for r in caplog.records)
    with served(hive.db, port=port) as server:
        import httpx
        from chatinho.support.parts.hive import KEY_HEADER

        def texts():
            answer = httpx.get(server.url + "/api/chats/team/messages", headers={KEY_HEADER: hive.admin})
            return [m["text"] for m in answer.json()["messages"]]

        await eventually(lambda: texts() == ["two", "three"], wait=40)
        await session.close()


# @ac AC-BACK-011.4
async def test_what_is_left_at_shutdown_is_lost_and_said(caplog):
    archive       = HiveBackend(down_url(), "hive_x", flush_timeout=0.5)
    session, view = await driven(backend=archive)
    await view.say("one")
    await view.say("two")
    started = time.monotonic()
    with caplog.at_level(logging.WARNING):
        await session.close()
    assert time.monotonic() - started < 0.5 + 1.0
    assert any("lost" in r.getMessage() and "2" in r.getMessage() for r in caplog.records)


# @ac AC-BACK-011.5
async def test_starting_without_the_hive(caplog):
    url = down_url()
    with caplog.at_level(logging.WARNING):
        session, view = await driven(backend=HiveBackend(url, "hive_x", flush_timeout=0.1))
    assert list(view.context()) == []
    assert any(url in r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING)
    await session.close()


# @ac AC-BACK-011.6
async def test_forgetting_without_the_hive_raises():
    archive = HiveBackend(down_url(), "hive_x", flush_timeout=0.1)
    await archive.initialize()
    try:
        with pytest.raises(HiveUnavailable):
            await archive.forget()
    finally:
        await archive.shutdown()


# @ac AC-BACK-011.6
async def test_linking_without_the_hive_is_none_with_a_warning(caplog):
    archive = HiveBackend(down_url(), "hive_x", flush_timeout=0.1)
    await archive.initialize()
    try:
        with caplog.at_level(logging.WARNING):
            assert await archive.link(message(1).id, "notes.md") is None
        assert any(r.levelno >= logging.WARNING for r in caplog.records)
    finally:
        await archive.shutdown()


# @ac AC-BACK-011.7
def test_a_bad_url_or_limit_is_refused():
    for url in ("ftp://hive", "hive.example", ""):
        with pytest.raises(ValueError):
            HiveBackend(url, "hive_x")
    for limit in (0, -1):
        with pytest.raises(ValueError):
            HiveBackend("http://hive", "hive_x", queue_limit=limit)


# @ac AC-BACK-012.1
async def test_a_wrong_key_is_one_error_never_logged_and_not_retried(tmp_path, caplog):
    hive  = make_hive(tmp_path, "team")
    wrong = "hive_" + "f" * 48
    with served(hive.db) as server:
        with caplog.at_level(logging.DEBUG):
            session, view = await driven(backend=HiveBackend(server.url, wrong, flush_timeout=5.0))
            caplog.clear()
            await view.say("one")
            await asyncio.sleep(2.0)
            started = time.monotonic()
            await session.close()
            took = time.monotonic() - started
    errors = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert len(errors) == 1
    assert server.url in errors[0].getMessage()
    assert all(wrong not in r.getMessage() for r in caplog.records)
    assert took < 2.0


# @ac AC-BACK-012.2
async def test_a_wrong_key_at_start(tmp_path, caplog):
    hive = make_hive(tmp_path, "team")
    with served(hive.db) as server:
        with caplog.at_level(logging.ERROR):
            wrong = HiveBackend(server.url, "hive_" + "0" * 48, flush_timeout=0.1)
            session, view = await driven(backend=wrong)
        assert list(view.context()) == []
        assert any(server.url in r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR)
        await session.close()
