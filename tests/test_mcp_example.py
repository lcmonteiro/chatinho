"""examples/mcp_server.py, started over stdio by an McpConnector."""

import pathlib
import sys

from chatinho.mcp import McpConnector
from conftest import driven

EXAMPLE = pathlib.Path(__file__).resolve().parent.parent / "examples" / "mcp_server.py"


async def _thinks(messages, *, max_tokens, system) -> str:
    return "thought about: %s" % messages[-1]["content"]


async def test_the_example_answers_over_stdio():
    lab = McpConnector(command=[sys.executable, str(EXAMPLE)], name="lab", sample_with=_thinks)
    session, view = await driven(connectors=[lab])
    assert await view.ask(lab.peer_id, "what is chatinho?") == "thought about: what is chatinho?"
    await session.close()


async def test_the_example_answers_without_a_model():
    lab = McpConnector(command=[sys.executable, str(EXAMPLE)], name="lab")
    session, view = await driven(connectors=[lab])
    assert (await view.ask(lab.peer_id, "hi")).startswith("You asked: hi")
    await session.close()
