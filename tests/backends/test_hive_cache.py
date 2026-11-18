"""
Tests for HiveBackend's local cache: the chat keeps its history offline, and nothing queued is lost.
"""

import asyncio
import json
import logging
import time

import httpx
import pytest

from chatinho import Attachment, HiveBackend, HookTrace, Trace, connector, require
from chatinho.support.parts.hive import KEY_HEADER
from conftest import driven
from fakes.hive import free_port, make_hive, message, served, wire_messages


@connector("rastro")
@require(HookTrace)
class _Tracer:
    trace : Trace


@pytest.fixture
def place(tmp_path):
    """A hive's database, a port to serve it on, and a cache file."""
    hive       = make_hive(tmp_path, "team")
    hive.port  = free_port()                                         # type: ignore[attr-defined]
    hive.url   = "http://127.0.0.1:%d" % hive.port                   # type: ignore[attr-defined]
    hive.cache = str(tmp_path / "team-cache.db")                     # type: ignore[attr-defined]
    return hive


def backend_of(place, **kwargs) -> HiveBackend:
    kwargs.setdefault("flush_timeout", 2.0)
    return HiveBackend(place.url, place.keys["team"], cache=place.cache, **kwargs)


async def eventually(check, wait: float = 10.0) -> None:
    deadline = time.monotonic() + wait
    while not check():
        if time.monotonic() > deadline:
            raise AssertionError("timed out waiting")
        await asyncio.sleep(0.1)


# @ac AC-BACK-013.1
async def test_history_offline(place, caplog):
    with served(place.db, port=place.port):
        session, view = await driven(backend=backend_of(place))
        said = [await view.say(text) for text in ("one", "two", "three")]
        await session.close()
    with caplog.at_level(logging.WARNING):
        session, view = await driven(backend=backend_of(place, flush_timeout=0.1))
    got = [m.id for m in view.context()]
    await session.close()
    assert got == said
    assert any("cache" in r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING)


# @ac AC-BACK-013.2
async def test_nothing_queued_is_lost_across_a_restart(place, caplog):
    tracer        = _Tracer()
    session, view = await driven(connectors=[tracer], backend=backend_of(place, flush_timeout=0.2))
    one  = await view.say("one")
    two  = await view.say("two")
    await asyncio.sleep(0.1)            # each listen is its own task: let both reach the backend first
    step = await tracer.trace(one, "running", "extract")
    with caplog.at_level(logging.WARNING):
        await session.close()
    assert any("kept" in r.getMessage() and "3" in r.getMessage() for r in caplog.records)
    got = []
    with served(place.db, port=place.port) as server:
        async with httpx.AsyncClient() as client:
            async with client.stream("GET", server.url + "/api/chats/team/stream",
                                     params={"key": place.admin},
                                     timeout=None) as stream:
                session, view = await driven(backend=backend_of(place))

                async def read():
                    async for line in stream.aiter_lines():
                        if line.startswith("data:"):
                            got.append(json.loads(line[5:])["id"])
                            if len(got) == 3:
                                return
                await asyncio.wait_for(read(), 20)
        await session.close()
    assert got == [str(one), str(two), str(step)]


# @ac AC-BACK-013.3
async def test_the_cache_follows_the_hive(place):
    messages = [message(n) for n in range(1, 4)]
    with served(place.db, port=place.port) as server:
        httpx.post(server.url + "/api/messages", json={"messages": wire_messages(*messages)},
                   headers={KEY_HEADER: place.keys["team"]})
        session, view = await driven(backend=backend_of(place))
        online = [m.id for m in view.context()]
        await session.close()
    session, view = await driven(backend=backend_of(place, flush_timeout=0.1))
    offline = [m.id for m in view.context()]
    await session.close()
    assert online == offline == [m.id for m in messages]


# @ac AC-BACK-013.4
async def test_forget_reaches_the_cache(place):
    messages = [message(n) for n in range(1, 6)]
    with served(place.db, port=place.port) as server:
        httpx.post(server.url + "/api/messages", json={"messages": wire_messages(*messages)},
                   headers={KEY_HEADER: place.keys["team"]})
        archive = backend_of(place)
        session, view = await driven(backend=archive)
        assert await archive.forget(before=messages[2].timestamp) == 2
        await session.close()
    session, view = await driven(backend=backend_of(place, flush_timeout=0.1))
    got = [m.id for m in view.context()]
    await session.close()
    assert got == [m.id for m in messages[2:]]


# @ac AC-BACK-013.5
async def test_an_attachment_offline(place):
    notes = Attachment(name="notes.md", media_type="text/markdown", data=b"# notes")
    with served(place.db, port=place.port):
        session, view = await driven(backend=backend_of(place))
        msg_id = await view.say("see [notes](notes.md)", attachments=[notes])
        await session.close()
    archive = backend_of(place, flush_timeout=0.1)
    session, view = await driven(backend=archive)
    try:
        path = await archive.link(msg_id, "notes.md")
        assert path is not None
        with open(path, "rb") as f:
            assert f.read() == b"# notes"
    finally:
        await session.close()


# @ac AC-BACK-013.6
async def test_a_cache_made_for_another_hive_is_refused(tmp_path):
    cache = str(tmp_path / "cache.db")
    first = HiveBackend("http://a:8700", "hive_x", cache=cache, flush_timeout=0.1)
    await first.initialize()
    await first.shutdown()
    other = HiveBackend("http://b:8700", "hive_x", cache=cache, flush_timeout=0.1)
    with pytest.raises(ValueError) as refused:
        await other.initialize()
    assert "http://a:8700" in str(refused.value) and "http://b:8700" in str(refused.value)
