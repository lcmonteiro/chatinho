"""examples/mcp_server.py, started over stdio by an McpConnector."""

import pathlib
import sys

from chatinho.connectors.mcp import McpConnector
from conftest import driven

EXAMPLE = pathlib.Path(__file__).resolve().parent.parent / "examples" / "mcp_server.py"


async def test_the_example_uses_a_lent_key_over_stdio():
    lab = McpConnector(command=[sys.executable, str(EXAMPLE)], name="lab", delegate={"llm": "sk-12345"})
    session, view = await driven(connectors=[lab])
    got = await view.ask(lab.peer_id, "what is chatinho?")
    assert got == "Thinking about 'what is chatinho?' with the key you lent (8 characters)"
    await session.close()


async def test_the_example_answers_without_a_key():
    lab = McpConnector(command=[sys.executable, str(EXAMPLE)], name="lab")
    session, view = await driven(connectors=[lab])
    assert (await view.ask(lab.peer_id, "hi")).startswith("You asked: hi")
    await session.close()
