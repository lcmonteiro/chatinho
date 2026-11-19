"""
Tests for watching a chat live: a server-sent event stream of what it stores.

They run against a hive served on a free port, since a stream is only a
stream over a real connection.
"""

import asyncio
import json
from datetime import timedelta
from typing import Any, Dict, List, Tuple

import httpx
import pytest

from chatinho import ChatTrace, TraceID, TraceState
from chatinho.support.parts.hive import KEY_HEADER, trace_to_wire
from fakes.hive import make_hive, message, served, wire_messages


@pytest.fixture
def hive(tmp_path):
    hive = make_hive(tmp_path, "a", "b")
    with served(hive.db) as server:
        hive.url = server.url                     # type: ignore[attr-defined]
        yield hive


async def events(response: httpx.Response, n: int, wait: float = 3.0) -> List[Tuple[str, Dict[str, Any]]]:
    """The first *n* events of *response*, or as many as arrive within *wait* seconds."""
    got   : List[Tuple[str, Dict[str, Any]]] = []
    kind  = None

    async def read() -> None:
        nonlocal kind
        async for line in response.aiter_lines():
            if line.startswith("event:"):
                kind = line.split(":", 1)[1].strip()
            elif line.startswith("data:") and kind is not None:
                got.append((kind, json.loads(line.split(":", 1)[1])))
                kind = None
                if len(got) >= n:
                    return

    try:
        await asyncio.wait_for(read(), wait)
    except asyncio.TimeoutError:
        pass
    return got


async def opened(client: httpx.AsyncClient, hive, chat: str, key: str):
    return client.stream("GET", "%s/api/chats/%s/stream" % (hive.url, chat), params={"key": key},
                         timeout=None)


# @ac AC-HIVE-007.1
async def test_a_message_and_then_a_trace_appear_in_order(hive):
    msg   = message(1)
    trace = ChatTrace(id=TraceID.new(), msg_id=msg.id, state=TraceState.RUNNING, text="extract", frm=1,
                      timestamp=msg.timestamp + timedelta(seconds=1))
    key   = {KEY_HEADER: hive.keys["a"]}
    async with httpx.AsyncClient() as client:
        async with await opened(client, hive, "a", hive.admin) as stream:
            assert stream.status_code == 200
            assert stream.headers["content-type"].startswith("text/event-stream")
            await asyncio.sleep(0.2)
            await client.post(hive.url + "/api/messages", json={"messages": wire_messages(msg)}, headers=key)
            await client.post(hive.url + "/api/traces", json={"traces": [trace_to_wire(trace, "dev")]},
                              headers=key)
            got = await events(stream, 2)
    assert [kind for kind, _ in got] == ["message", "trace"]
    assert got[0][1]["id"] == str(msg.id) and got[0][1]["text"] == msg.text
    assert got[1][1]["id"] == str(trace.id) and got[1][1]["msg_id"] == str(msg.id)


# @ac AC-HIVE-007.1
async def test_a_resend_is_not_streamed_again(hive):
    msg = message(1)
    key = {KEY_HEADER: hive.keys["a"]}
    async with httpx.AsyncClient() as client:
        async with await opened(client, hive, "a", hive.admin) as stream:
            await asyncio.sleep(0.2)
            for _ in range(2):
                await client.post(hive.url + "/api/messages", json={"messages": wire_messages(msg)},
                                  headers=key)
            got = await events(stream, 2, wait=1.5)
    assert [kind for kind, _ in got] == ["message"]


# @ac AC-HIVE-007.2
async def test_another_chat_is_not_shown(hive):
    async with httpx.AsyncClient() as client:
        async with await opened(client, hive, "a", hive.admin) as stream:
            await asyncio.sleep(0.2)
            await client.post(hive.url + "/api/messages", json={"messages": wire_messages(message(1))},
                              headers={KEY_HEADER: hive.keys["b"]})
            got = await events(stream, 1, wait=1.0)
    assert got == []


# @ac AC-HIVE-007.3
async def test_a_chat_key_cannot_watch(hive):
    async with httpx.AsyncClient() as client:
        async with await opened(client, hive, "a", hive.keys["a"]) as stream:
            assert stream.status_code == 403


# @ac AC-HIVE-007.3
async def test_a_stream_without_a_key_is_401(hive):
    async with httpx.AsyncClient() as client:
        answer = await client.get(hive.url + "/api/chats/a/stream", timeout=5)
    assert answer.status_code == 401
