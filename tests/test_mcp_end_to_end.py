"""Two chatinho sessions, one asking the other over the modern MCP protocol."""

import asyncio

from chatinho import (
    LOCAL,
    Attachment,
    ChatSession,
    Context,
    HookContext,
    HookListen,
    HookSay,
    Say,
    frontend,
    require,
)
from chatinho.connectors.mcp import McpConnector
from chatinho.frontends.mcp import McpFrontend
from mcp_kit import Agent, Files, Weather


@frontend("me")
@require(HookSay)
@require(HookListen)
@require(HookContext)
class Me:
    """The person at the asking session's terminal."""

    say     : Say
    context : Context

    async def listen(self, msg) -> None:
        pass


async def _until(me: Me, count: int) -> list:
    for _ in range(250):
        if len(me.context()) >= count:
            break
        await asyncio.sleep(0.02)
    return me.context()


async def test_a_question_crosses_with_a_lent_key_and_returns_with_its_drawing(tmp_path):
    chart  = Attachment("chart.svg", "image/svg+xml", b"<svg>login</svg>")
    agent  = Agent(key=True, attach=chart)
    front  = McpFrontend(token="t", credentials={"llm": "OpenAI-compatible API key"})
    there  = ChatSession(frontend=front, connectors=[agent], backend=Files(tmp_path / "there"))
    await there.start()

    me     = Me()
    lab    = McpConnector(server=front.server, name="lab", delegate={"llm": "sk-lent"})
    here   = ChatSession(frontend=me, backend=Files(tmp_path / "here"), connectors=[lab])
    await here.start()

    await me.say("@lab draw the login flow")
    reply = (await _until(me, 2))[-1]

    assert reply.text.startswith("agent: draw the login flow")
    assert agent.keys == ["sk-lent"]
    assert all("sk-lent" not in m.text for m in there._context() + me.context())
    assert "[chart](chart.svg)" in reply.text
    assert (tmp_path / "here" / str(reply.id) / "chart.svg").read_bytes() == b"<svg>login</svg>"
    asked = [m for m in there._context() if m.text == "draw the login flow"][0]
    assert asked.frm == LOCAL and asked.to == agent.peer_id

    await here.close()
    await there.close()


async def test_with_two_peers_the_question_is_said_in_the_remote_room():
    front  = McpFrontend(token="t")
    there  = ChatSession(frontend=front, connectors=[Agent("agent"), Weather()])
    await there.start()
    me     = Me()
    here   = ChatSession(frontend=me, connectors=[McpConnector(server=front.server, name="lab")])
    await here.start()

    await me.say("@lab who can draw?")
    reply = (await _until(me, 2))[-1]

    assert reply.text == "agent: who can draw?"
    said = [m for m in there._context() if m.text == "who can draw?"][0]
    assert said.is_broadcast and said.frm == LOCAL

    await here.close()
    await there.close()
