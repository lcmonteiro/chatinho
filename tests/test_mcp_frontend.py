"""McpFrontend: a bridge with one tool, say, over the modern MCP protocol."""

import asyncio
import time

import pytest

from chatinho import LOCAL, Attachment, HookAnswer, HookAsk, Reply, connector, require
from chatinho.connectors.mcp import _decode, _read_result
from chatinho.frontends.mcp import CREDENTIALS_KEY, McpFrontend
from mcp_kit import Agent, Files, Weather, client, remote, say


# === The frontend itself ===========================================================

async def test_named_master_by_default():
    session, front = await remote(Weather())
    assert front.name == "master"
    assert session._peers()[0] is front
    async with client(front) as c:
        assert c.server_info.name == "master"
        assert c.session.protocol_version == "2026-07-28"
    await session.close()


def test_a_token_is_required():
    with pytest.raises(ValueError):
        McpFrontend(token="")
    with pytest.raises(TypeError):
        McpFrontend()                                   # type: ignore[call-arg]


async def test_one_tool_say():
    session, front = await remote(Weather())
    async with client(front) as c:
        tools = (await c.list_tools()).tools
        other = await c.call_tool("ask", {"text": "?"})
    assert [t.name for t in tools] == ["say"]
    assert set(tools[0].input_schema["properties"]) == {"text", "asker", "deadline_ms"}
    assert _read_result(other).status == "error"
    await session.close()


async def test_answered():
    session, front = await remote(Weather("sunny"))
    async with client(front) as c:
        got = await say(c, "will it rain?")
    assert (got["status"], got["text"]) == ("answered", "sunny")
    await session.close()


async def test_no_reply_in_time():
    session, front = await remote(Weather(delay=0.6))
    started = time.monotonic()
    async with client(front) as c:
        got = await say(c, "slow?", deadline_ms=200)
    assert got["status"] == "timeout"
    assert time.monotonic() - started < 2
    await session.close()


async def test_the_default_deadline_is_configurable():
    session, front = await remote(Weather(delay=0.6), deadline=0.2)
    async with client(front) as c:
        got = await say(c, "slow?")
    assert got["status"] == "timeout"
    await session.close()


async def test_answered_with_a_question():
    session, front = await remote(Weather(Reply("which login flow?", status="asked")))
    async with client(front) as c:
        got = await say(c, "draw it")
    assert (got["status"], got["text"]) == ("asked", "which login flow?")
    await session.close()


async def test_a_failing_peer_is_an_error():
    session, front = await remote(Weather(RuntimeError("boom")))
    async def boom(msg):
        raise RuntimeError("boom")
    session._peers()[1].answer = boom
    async with client(front) as c:
        got = await say(c, "?")
    assert got["status"] == "error" and "failed" in got["text"]
    await session.close()


async def test_attachments_come_back(tmp_path):
    chart = Attachment("chart.svg", "image/svg+xml", b"<svg/>")
    session, front = await remote(Agent(attach=chart), backend=Files(tmp_path))
    async with client(front) as c:
        got = await say(c, "draw it")
    assert got["status"] == "answered"
    assert [_decode(a) for a in got["attachments"]] == [chart]
    await session.close()


# === A bridge for every client ======================================================

@connector("echo")
@require(HookAnswer)
class _Echo:
    """Answers each message with itself, a little later."""

    async def answer(self, msg):
        await asyncio.sleep(0.1)
        return "echo: %s" % msg.text


async def test_the_reply_goes_back_to_its_client():
    weather = Weather("sunny")
    session, front = await remote(weather)
    async with client(front, "lab") as c:
        got = await say(c, "will it rain?", asker="me")
    assert got["text"] == "sunny"
    assert weather.asked[0].frm == LOCAL
    await session.close()


async def test_two_clients_at_once():
    session, front = await remote(_Echo())
    before = set(session._peers())
    async with client(front, "lab") as one, client(front, "home") as two:
        first, second = await asyncio.gather(say(one, "from lab"), say(two, "from home"))
    assert (first["text"], second["text"]) == ("echo: from lab", "echo: from home")
    assert set(session._peers()) == before
    await session.close()


async def test_asking_the_frontend():
    @connector("curious")
    @require(HookAsk)
    class _Curious:
        pass

    curious = _Curious()
    session, front = await remote(Weather(), curious)
    got = await curious.ask(LOCAL, "anyone there?")
    assert "Nobody" in got
    assert session._context()[-1].status == "error"
    await session.close()


# === Who replies ===================================================================

async def test_the_only_peer_is_asked():
    weather = Weather()
    session, front = await remote(weather)
    async with client(front) as c:
        await say(c, "rain?")
    assert weather.asked[0].to == weather.peer_id
    await session.close()


async def test_with_several_peers_it_is_said_and_the_first_reply_answers():
    session, front = await remote(Agent(), Weather())
    async with client(front) as c:
        got = await say(c, "draw the login flow")
    assert got["status"] == "answered" and got["text"] == "agent: draw the login flow"
    said = [m for m in session._context() if m.text == "draw the login flow"][0]
    assert said.is_broadcast
    await session.close()


async def test_the_first_reply_wins_and_the_second_stays():
    session, front = await remote(Agent("fast"), Agent("slow", delay=0.2))
    async with client(front) as c:
        got = await say(c, "who?")
        await asyncio.sleep(0.4)
    assert got["text"] == "fast: who?"
    assert "slow: who?" in [m.text for m in session._context()]
    await session.close()


async def test_several_peers_and_none_listens():
    session, front = await remote(Weather(), Weather())
    async with client(front) as c:
        got = await say(c, "?")
    assert got["status"] == "error" and "router" in got["text"]
    await session.close()


async def test_no_peer():
    session, front = await remote()
    async with client(front) as c:
        got = await say(c, "?")
    assert got["status"] == "error" and "No peer" in got["text"]
    await session.close()


async def test_a_follow_up_goes_to_the_same_peer():
    weather = Weather(Reply("which city?", status="asked"))
    session, front = await remote(weather)
    async with client(front) as c:
        assert (await say(c, "rain?", asker="me"))["status"] == "asked"
        await say(c, "Lisbon", asker="me")
    assert [m.text for m in weather.asked] == ["rain?", "Lisbon"]
    assert weather.asked[0].frm == weather.asked[1].frm == LOCAL
    await session.close()


async def test_a_follow_up_in_the_room_replies_to_the_last_reply():
    session, front = await remote(Agent("a"), Agent("b", replies=False))
    async with client(front) as c:
        got = await say(c, "rain?", asker="me")
        await say(c, "Lisbon", asker="me")
    said  = [m for m in session._context() if m.text == "Lisbon"][0]
    first = [m for m in session._context() if m.text == got["text"]][0]
    assert said.reply_to == first.id
    await session.close()


# === Credentials ===================================================================

async def _lend(c, value="sk-test", **args):
    lent = {CREDENTIALS_KEY: {"llm": value, "cloud": "x"}}
    res  = await c.call_tool("say", {"text": "go", **args}, meta=lent)
    return res.structured_content


async def test_declared_at_discovery():
    session, front = await remote(Weather(), credentials={"llm": "OpenAI-compatible API key"})
    async with client(front) as c:
        found = c.session.discover_result.capabilities.extensions
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
        await say(c, "no key")
    assert agent.keys == ["sk-one", "sk-two", None]
    await session.close()


async def test_a_credential_is_gone_on_timeout():
    agent = Agent(key=False, delay=0.3)
    session, front = await remote(agent, credentials={"llm": "key"})
    async with client(front) as c:
        got = await _lend(c, deadline_ms=100)
    assert got["status"] == "timeout"
    said = [m for m in session._context() if m.text == "go"][0]
    assert said.credentials == {}                   # cleared at the deadline, while the peer still works
    await session.close()


async def test_a_credential_is_never_in_the_conversation():
    agent = Agent(key=True)
    session, front = await remote(agent, credentials={"llm": "key"})
    async with client(front) as c:
        await _lend(c, value="sk-very-secret")
    assert all("sk-very-secret" not in m.text for m in session._context())
    assert "sk-very-secret" not in repr(front._lent({CREDENTIALS_KEY: {"llm": "sk-very-secret"}}))
    await session.close()
