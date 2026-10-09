"""McpFrontend: ask, peers, tools and invoke as MCP tools, over the modern MCP protocol."""

import asyncio

import pytest

from chatinho import LOCAL, Attachment, HookAnswer, HookExecute, Reply, connector, declares, require, tool
from chatinho.frontends.mcp import McpFrontend
from chatinho.helpers.mcp import CREDENTIALS_KEY, decode
from mcp_kit import Agent, Files, Weather, ask, call, client, remote


# === The frontend itself ===========================================================

async def test_named_master_by_default():
    session, front = await remote(Weather())
    assert front.name == "master"
    assert session._peers()[0] is front
    async with client(front) as c:
        assert c.server_info.name == "master"
        assert c.protocol_version == "2026-07-28"
    await session.close()


def test_a_token_is_required():
    with pytest.raises(ValueError):
        McpFrontend(token="")
    with pytest.raises(TypeError):
        McpFrontend()                                   # type: ignore[call-arg]


async def test_what_a_terminal_can_do():
    session, front = await remote(Weather())
    async with client(front) as c:
        tools = {t.name: t for t in await c.list_tools()}
        other = await c.call_tool_mcp("forget", {})
    assert list(tools) == ["ask", "peers", "tools", "invoke"]
    assert set(tools["ask"].input_schema["properties"]) == {"peer", "text"}
    assert set(tools["invoke"].input_schema["properties"]) == {"name", "args"}
    assert other.is_error
    await session.close()


async def test_answered():
    session, front = await remote(Weather("sunny"))
    async with client(front) as c:
        got = await ask(c, "weather", "will it rain?")
    assert (got["status"], got["text"]) == ("answered", "sunny")
    await session.close()


async def test_answered_with_a_question():
    session, front = await remote(Weather(Reply("which login flow?", status="asked")))
    async with client(front) as c:
        got = await ask(c, "weather", "draw it")
    assert (got["status"], got["text"]) == ("asked", "which login flow?")
    await session.close()


async def test_a_failing_peer_is_an_error():
    session, front = await remote(Weather(RuntimeError("boom")))
    async def boom(msg):
        raise RuntimeError("boom")
    session._peers()[1].answer = boom
    async with client(front) as c:
        got = await ask(c, "weather", "?")
    assert got["status"] == "error" and "failed" in got["text"]
    await session.close()


async def test_attachments_come_back(tmp_path):
    chart = Attachment("chart.svg", "image/svg+xml", b"<svg/>")
    session, front = await remote(Agent(attach=chart), backend=Files(tmp_path))
    async with client(front) as c:
        got = await ask(c, "agent", "draw it")
    assert got["status"] == "answered"
    assert [decode(a) for a in got["attachments"]] == [chart]
    await session.close()


# === A bridge for every client ======================================================

@connector("echo")
@require(HookAnswer)
class _Echo:
    """Answers each message with itself, a little later."""

    async def answer(self, msg):
        await asyncio.sleep(0.1)
        return Reply("echo: %s" % msg.text)


async def test_the_reply_goes_back_to_its_client():
    weather = Weather("sunny")
    session, front = await remote(weather)
    async with client(front, "lab") as c:
        got = await ask(c, "weather", "will it rain?")
    assert got["text"] == "sunny"
    assert weather.asked[0].frm == LOCAL
    await session.close()


async def test_two_clients_at_once():
    session, front = await remote(_Echo())
    before = set(session._peers())
    async with client(front, "lab") as one, client(front, "home") as two:
        first, second = await asyncio.gather(ask(one, "echo", "from lab"), ask(two, "echo", "from home"))
    assert (first["text"], second["text"]) == ("echo: from lab", "echo: from home")
    assert set(session._peers()) == before
    await session.close()


def test_the_frontend_is_never_asked():
    assert not declares(McpFrontend(token="t"), HookAnswer)


# === Asking one peer ===============================================================

async def test_ask_a_peer_by_name():
    agent, weather = Agent(), Weather("sunny")
    session, front = await remote(agent, weather)
    async with client(front) as c:
        got = await call(c, "ask", peer="weather", text="rain?")
    assert (got["status"], got["text"]) == ("answered", "sunny")
    assert [m.text for m in weather.asked] == ["rain?"]
    assert weather.asked[0].to == weather.peer_id
    assert not any(m.text == "rain?" for m in agent.heard if m.to is None)
    await session.close()


async def test_ask_keeps_the_status():
    session, front = await remote(Agent(), Weather(Reply("which city?", status="asked")))
    async with client(front) as c:
        got = await call(c, "ask", peer="weather", text="rain?")
    assert (got["status"], got["text"]) == ("asked", "which city?")
    await session.close()


async def test_ask_a_peer_that_fails():
    session, front = await remote(Agent(), Weather(RuntimeError("boom")))
    async def boom(msg):
        raise RuntimeError("boom")
    session._peers()[2].answer = boom
    async with client(front) as c:
        got = await call(c, "ask", peer="weather", text="?")
    assert got["status"] == "error" and "failed" in got["text"]
    await session.close()


@connector("mute")
class _Mute:
    """In the session, but answers nothing."""


@pytest.mark.parametrize("peers, peer, says", [
    ((Weather(),), "nobody", "No peer named"),
    ((Weather(), _Mute()), "mute", "does not answer"),
    ((Weather(), Weather()), "weather", "Several peers"),
    ((Weather(),), "master", "No peer named"),
])
async def test_ask_who_cannot_answer(peers, peer, says):
    session, front = await remote(*peers)
    async with client(front) as c:
        got = await call(c, "ask", peer=peer, text="?")
    assert got["status"] == "error" and says in got["text"]
    await session.close()


async def test_ask_lends_credentials():
    agent = Agent(key=True)
    session, front = await remote(agent, Weather(), credentials={"llm": "key"})
    async with client(front) as c:
        await c.call_tool_mcp("ask", {"peer": "agent", "text": "go"}, meta={CREDENTIALS_KEY: {"llm": "sk-a"}})
    assert agent.keys == ["sk-a"]
    assert [m for m in session._context() if m.text == "go"][0].credentials == {}
    await session.close()


# === The roster and the tools =======================================================

@tool("eco", "Repeats what it is given")
@require(HookExecute)
class _EcoTool:
    def __init__(self, delay=0.0):
        self.delay = delay

    async def execute(self, args="", by=LOCAL, **kwargs):
        await asyncio.sleep(self.delay)
        return Reply("eco: %s" % args)


async def test_peers():
    session, front = await remote(Agent(), Weather(), _Mute())
    async with client(front) as c:
        result = await c.call_tool("peers")
    assert [(p.name, p.answers) for p in result.data] == [("agent", True), ("weather", True), ("mute", False)]
    await session.close()


async def test_tools():
    session, front = await remote(Weather(), commands=[_EcoTool()])
    async with client(front) as c:
        result = await c.call_tool("tools")
    assert [(t.name, t.description) for t in result.data] == [("eco", "Repeats what it is given")]
    await session.close()


async def test_invoke_a_tool():
    session, front = await remote(Weather(), commands=[_EcoTool()])
    async with client(front) as c:
        got   = await call(c, "invoke", name="eco", args="hi")
        slash = await call(c, "invoke", name="/eco")
    assert (got["status"], got["text"]) == ("answered", "eco: hi")
    assert slash["text"] == "eco: "
    assert "/eco hi" in [m.text for m in session._context()]
    await session.close()


async def test_invoke_a_tool_that_does_not_exist():
    session, front = await remote(Weather())
    async with client(front) as c:
        got = await call(c, "invoke", name="nope")
    assert got["status"] == "error" and "No tool named" in got["text"]
    await session.close()


# === Credentials ===================================================================

async def _lend(c, value="sk-test", **args):
    lent = {CREDENTIALS_KEY: {"llm": value, "cloud": "x"}}
    res  = await c.call_tool_mcp("ask", {"peer": "agent", "text": "go", **args}, meta=lent)
    return res.structured_content


async def test_declared_at_discovery():
    session, front = await remote(Weather(), credentials={"llm": "OpenAI-compatible API key"})
    async with client(front) as c:
        found = c.server_capabilities.extensions
    assert found[CREDENTIALS_KEY] == {"llm": "OpenAI-compatible API key"}
    await session.close()


async def test_a_lent_credential_reaches_the_peer_and_undeclared_ones_do_not():
    agent = Agent(key=True)
    session, front = await remote(agent, credentials={"llm": "key"})
    async with client(front) as c:
        await _lend(c)
    assert agent.keys == ["sk-test"]
    assert front._lent({CREDENTIALS_KEY: {"cloud": "x"}}) == {}
    await session.close()


async def test_a_credential_is_gone_after_the_reply():
    agent = Agent(key=True)
    session, front = await remote(agent, credentials={"llm": "key"})
    async with client(front) as c:
        await _lend(c)
    said = [m for m in session._context() if m.text == "go"][0]
    assert said.credentials == {}
    await session.close()


async def test_each_message_brings_its_own_key():
    agent = Agent(key=True)
    session, front = await remote(agent, credentials={"llm": "key"})
    async with client(front) as c:
        await _lend(c, value="sk-one")
        await _lend(c, value="sk-two")
        await ask(c, "agent", "no key")
    assert agent.keys == ["sk-one", "sk-two", None]
    await session.close()


async def test_a_credential_is_gone_when_the_client_gives_up():
    agent = Agent(key=False, delay=0.5)
    session, front = await remote(agent, credentials={"llm": "key"})
    async with client(front) as c:
        with pytest.raises(Exception):
            await c.call_tool_mcp("ask", {"peer": "agent", "text": "go"}, timeout=0.1,
                                  meta={CREDENTIALS_KEY: {"llm": "sk-test"}})
        await asyncio.sleep(0.1)
    said = [m for m in session._context() if m.text == "go"][0]
    assert said.credentials == {}                   # cleared when the call ended, while the peer still works
    await session.close()


async def test_a_credential_is_never_in_the_conversation():
    agent = Agent(key=True)
    session, front = await remote(agent, credentials={"llm": "key"})
    async with client(front) as c:
        await _lend(c, value="sk-very-secret")
    assert all("sk-very-secret" not in m.text for m in session._context())
    assert "sk-very-secret" not in repr(front._lent({CREDENTIALS_KEY: {"llm": "sk-very-secret"}}))
    await session.close()
