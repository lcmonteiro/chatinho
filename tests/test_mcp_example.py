"""examples/mcp_server.py, started as its own process and asked over HTTP."""

import asyncio
import os
import pathlib
import socket
import sys

import pytest

from chatinho.connectors.mcp import McpConnector
from conftest import driven

EXAMPLE = pathlib.Path(__file__).resolve().parent.parent / "examples" / "mcp_server.py"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
async def served():
    """The example, listening on a free port; yields its URL."""
    port = _free_port()
    proc = await asyncio.create_subprocess_exec(
        sys.executable, str(EXAMPLE), str(port),
        env={**os.environ, "CHATINHO_MCP_TOKEN": "s3cret"},
    )
    for _ in range(200):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                break
        except OSError:
            await asyncio.sleep(0.05)
    yield "http://127.0.0.1:%d/mcp" % port
    proc.terminate()
    await proc.wait()


async def test_the_example_uses_a_lent_key(served):
    lab = McpConnector(url=served, token="s3cret", name="lab", delegate={"llm": "sk-12345"})
    session, view = await driven(connectors=[lab])
    got = await view.ask(lab.peer_id, "what is chatinho?")
    assert got == "Thinking about 'what is chatinho?' with the key you lent (8 characters)"
    await session.close()


async def test_the_example_answers_without_a_key(served):
    lab = McpConnector(url=served, token="s3cret", name="lab")
    session, view = await driven(connectors=[lab])
    assert (await view.ask(lab.peer_id, "hi")).startswith("You asked: hi")
    await session.close()
