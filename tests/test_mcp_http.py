"""McpFrontend over Streamable HTTP: no request without the bearer token."""

import asyncio
import socket

import httpx2
import mcp_types as types
import pytest
from fastmcp import Client

from chatinho import ChatSession
from chatinho.connectors.mcp import McpConnector
from chatinho.frontends.mcp import McpFrontend
from chatinho.keys import Env, KeyUnavailable
from conftest import driven
from mcp_kit import Weather


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def _serving(front: McpFrontend) -> asyncio.Task:
    task = asyncio.create_task(front.serve())
    for _ in range(100):
        try:
            with socket.create_connection((front.host, front.port), timeout=0.1):
                return task
        except OSError:
            await asyncio.sleep(0.05)
    raise RuntimeError("the server never came up")


async def test_http_refuses_requests_without_the_token_and_serves_those_with_it():
    front   = McpFrontend(port=_free_port(), token="s3cret")
    session = ChatSession(frontend=front, connectors=[Weather("sunny")])
    await session.start()
    serving = await _serving(front)
    url     = "http://127.0.0.1:%d/mcp" % front.port
    try:
        async with httpx2.AsyncClient() as http:
            bare  = await http.post(url, json={"jsonrpc": "2.0", "id": 1, "method": "server/discover"})
            wrong = await http.post(url, json={}, headers={"Authorization": "Bearer nope"})
        assert bare.status_code == 401 and wrong.status_code == 401

        async with Client(url, auth="s3cret", client_info=types.Implementation(name="lab", version="1")) as c:
            version = c.protocol_version
            res     = await c.call_tool_mcp("ask", {"peer": "weather", "text": "rain?"})
        assert res.structured_content["text"] == "sunny"
        assert version == "2026-07-28"
    finally:
        front.shutdown()
        await asyncio.wait_for(serving, 5)
        await session.close()


async def test_tokens_from_key_sources(monkeypatch):
    monkeypatch.setenv("CHATINHO_MCP_TOKEN", "s3cret")
    front   = McpFrontend(port=_free_port(), token=Env("CHATINHO_MCP_TOKEN"))
    session = ChatSession(frontend=front, connectors=[Weather("sunny")])
    await session.start()
    serving = await _serving(front)
    url     = "http://127.0.0.1:%d/mcp" % front.port
    try:
        async with httpx2.AsyncClient() as http:
            wrong = await http.post(url, json={}, headers={"Authorization": "Bearer nope"})
        assert wrong.status_code == 401
        lab = McpConnector(url=url, token=Env("CHATINHO_MCP_TOKEN"), name="lab")
        here, view = await driven(connectors=[lab])
        try:
            assert await view.ask(lab.peer_id, "rain?") == "sunny"
        finally:
            await here.close()
    finally:
        front.shutdown()
        await asyncio.wait_for(serving, 5)
        await session.close()


def test_a_missing_token_fails_at_startup(monkeypatch):
    monkeypatch.delenv("UNSET", raising=False)
    with pytest.raises(KeyUnavailable, match="UNSET"):
        McpFrontend(token=Env("UNSET"))
    with pytest.raises(KeyUnavailable, match="UNSET"):
        McpConnector(url="http://127.0.0.1:1/mcp", token=Env("UNSET"))
