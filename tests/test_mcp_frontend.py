"""McpFrontend: a session served over the modern MCP protocol."""

import asyncio
import time

import pytest

from chatinho import LOCAL, Attachment, HookAnswer, HookAsk, Reply, connector, require
from chatinho import mcp_wire as wire
from chatinho.frontends.mcp import McpFrontend
from mcp_kit import Agent, Files, Weather, ask, client, remote


# === The frontend itself ===========================================================

async def test_named_master_by_default():
    session, front = await remote(Weather())
    assert front.name == "master"
    assert session._peers()[0] is front
    async with client(front) as c:
        assert c.server_info.name == "master"
        assert c.session.protocol_version == "2026-07-28"
    await session.close()


def test_http_needs_a_token():
    with pytest.raises(ValueError):
        McpFrontend(transport="http")
    with pytest.raises(ValueError):
        McpFrontend(transport="carrier-pigeon")


async def test_no_tool_broadcasts_and_ask_names_no_peer():
    session, front = await remote(Weather())
    async with client(front) as c:
        tools = {t.name: t for t in (await c.list_tools()).tools}
    assert set(tools) == {"ask", "list_peers", "list_commands", "invoke", "read_attachment"}
    assert set(tools["ask"].input_schema["properties"]) == {"text", "asker", "deadline_ms"}
    await session.close()


async def test_listing_peers_leaves_out_the_frontend_and_the_askers():
    session, front = await remote(Agent(), Weather())
    async with client(front) as c:
        await ask(c, "hello", asker="me")
        res = await c.call_tool("list_peers", {})
    assert res.structured_content["peers"] == ["agent", "weather"]
    await session.close()


async def test_answered():
    session, front = await remote(Weather("sunny"))
    async with client(front) as c:
        got = await ask(c, "will it rain?")
    assert (got["status"], got["text"]) == ("answered", "sunny")
    await session.close()


async def test_nobody_answers_in_time():
    session, front = await remote(Weather(delay=0.6))
    started = time.monotonic()
    async with client(front) as c:
        got = await ask(c, "slow?", deadline_ms=200)
    assert got["status"] == "timeout"
    assert time.monotonic() - started < 2
    await session.close()


async def test_the_default_deadline_is_configurable():
    session, front = await remote(Weather(delay=0.6), deadline=0.2)
    async with client(front) as c:
        got = await ask(c, "slow?")
    assert got["status"] == "timeout"
    await session.close()


async def test_answered_with_a_question():
    session, front = await remote(Weather(Reply("which login flow?", status="asked")))
    async with client(front) as c:
        got = await ask(c, "draw it")
    assert (got["status"], got["text"]) == ("asked", "which login flow?")
    await session.close()


async def test_a_failing_peer_is_an_error():
    session, front = await remote(Weather(RuntimeError("boom")))
    async def boom(msg):
        raise RuntimeError("boom")
    session._peers()[1].answer = boom
    async with client(front) as c:
        got = await ask(c, "?")
    assert got["status"] == "error" and "failed" in got["text"]
    await session.close()


async def test_attachments_come_back(tmp_path):
    chart = Attachment("chart.svg", "image/svg+xml", b"<svg/>")
    session, front = await remote(Agent(attach=chart), backend=Files(tmp_path))
    async with client(front) as c:
        got = await ask(c, "draw it")
        assert got["status"] == "answered"
        [item] = [wire.decode(a) for a in got["attachments"]]
        assert item == chart
        again = await c.call_tool("read_attachment", {"msg_id": got["msg_id"], "name": "chart.svg"})
        assert wire.read_result(again).attachments == (chart,)
    await session.close()


async def test_commands_run_from_the_client():
    from chatinho import HelpCommand
    front   = McpFrontend()
    from chatinho import ChatSession
    session = ChatSession(frontend=front, connectors=[Weather()], commands=[HelpCommand()])
    await session.start()
    async with client(front) as c:
        listed = await c.call_tool("list_commands", {})
        ran    = await c.call_tool("invoke", {"name": "help"})
        none   = await c.call_tool("invoke", {"name": "nope"})
    assert "help" in [cmd["name"] for cmd in listed.structured_content["commands"]]
    assert wire.read_result(ran).status == "answered"
    assert wire.read_result(none).status == "error"
    await session.close()


# === The frontend speaks for every client ==========================================

@connector("echo")
@require(HookAnswer)
class _Echo:
    """Answers each question with itself, a little later."""

    async def answer(self, msg):
        await asyncio.sleep(0.1)
        return "echo: %s" % msg.text


async def test_the_reply_goes_back_to_its_client():
    weather = Weather("sunny")
    session, front = await remote(weather)
    async with client(front, "lab") as c:
        got = await ask(c, "will it rain?", asker="me")
    assert got["text"] == "sunny"
    assert weather.asked[0].frm == LOCAL
    await session.close()


async def test_two_clients_at_once():
    session, front = await remote(_Echo())
    before = set(session._peers())
    async with client(front, "lab") as one, client(front, "home") as two:
        first, second = await asyncio.gather(ask(one, "from lab"), ask(two, "from home"))
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
    got = await curious.ask(LOCAL, "anyone there?", detail=True)
    assert got.status == "error" and "Nobody" in got.text
    await session.close()


# === Who answers ===================================================================

async def test_the_only_peer_is_asked_directly():
    weather = Weather()
    session, front = await remote(weather)
    async with client(front) as c:
        await ask(c, "rain?")
    assert weather.asked[0].to == weather.peer_id
    await session.close()


async def test_with_several_peers_the_question_is_said_and_the_first_reply_answers():
    agent = Agent(delay=0.0)
    session, front = await remote(agent, Weather())
    async with client(front) as c:
        got = await ask(c, "draw the login flow")
    assert got["status"] == "answered" and got["text"] == "agent: draw the login flow"
    said = [m for m in session._context() if m.text == "draw the login flow"][0]
    assert said.is_broadcast
    await session.close()


async def test_the_first_reply_wins_and_the_second_stays():
    session, front = await remote(Agent("fast"), Agent("slow", delay=0.2))
    async with client(front) as c:
        got = await ask(c, "who?")
        await asyncio.sleep(0.4)
    assert got["text"] == "fast: who?"
    assert "slow: who?" in [m.text for m in session._context()]
    await session.close()


async def test_several_peers_and_none_listens():
    session, front = await remote(Weather(), Weather())
    async with client(front) as c:
        got = await ask(c, "?")
    assert got["status"] == "error" and "router" in got["text"]
    await session.close()


async def test_no_peer():
    session, front = await remote()
    async with client(front) as c:
        got = await ask(c, "?")
    assert got["status"] == "error" and "No peer" in got["text"]
    await session.close()


async def test_a_follow_up_goes_to_the_same_peer():
    weather = Weather(Reply("which city?", status="asked"))
    session, front = await remote(weather)
    async with client(front) as c:
        assert (await ask(c, "rain?", asker="me"))["status"] == "asked"
        await ask(c, "Lisbon", asker="me")
    assert [m.text for m in weather.asked] == ["rain?", "Lisbon"]
    assert weather.asked[0].frm == weather.asked[1].frm == LOCAL
    await session.close()


async def test_a_follow_up_in_the_room_replies_to_the_last_answer():
    session, front = await remote(Agent("a"), Agent("b", replies=False))
    first_reply = Reply("which city?", status="asked")
    async with client(front) as c:
        session._peers()[1]._respond = _once(first_reply, session._peers()[1]._respond)
        got = await ask(c, "rain?", asker="me")
        assert got["status"] == "answered"          # a reply in the room carries no status
        follow = await ask(c, "Lisbon", asker="me")
    assert follow["status"] == "answered"
    said = [m for m in session._context() if m.text == "Lisbon"][0]
    asked_back = [m for m in session._context() if m.text == got["text"]][0]
    assert said.reply_to == asked_back.id
    await session.close()


def _once(reply, then):
    """Answers *reply* the first time, then falls back to *then*."""
    calls = []

    async def respond(msg):
        calls.append(msg)
        return reply if len(calls) == 1 else await then(msg)
    return respond


# === Credentials ===================================================================

async def _lend(c, value="sk-test", **args):
    lent = {wire.CREDENTIALS_KEY: {"llm": value, "cloud": "x"}}
    res  = await c.call_tool("ask", {"text": "go", **args}, meta=lent)
    return res.structured_content


async def test_declared_at_discovery():
    session, front = await remote(Weather(), credentials={"llm": "OpenAI-compatible API key"})
    async with client(front) as c:
        found = c.session.discover_result.capabilities.extensions
    assert found[wire.CREDENTIALS_KEY] == {"llm": "OpenAI-compatible API key"}
    await session.close()


async def test_a_lent_credential_reaches_the_peer_and_undeclared_ones_do_not():
    agent = Agent(key=True)
    session, front = await remote(agent, credentials={"llm": "key"})
    async with client(front) as c:
        await _lend(c)
    assert agent.keys == ["sk-test"]
    assert front._lent({wire.CREDENTIALS_KEY: {"cloud": "x"}}) == {}
    await session.close()


async def test_a_credential_is_gone_after_the_answer():
    agent = Agent(key=True)
    session, front = await remote(agent, credentials={"llm": "key"})
    async with client(front) as c:
        await _lend(c)
    question_id = [m for m in session._context() if m.text == "go"][0].id
    from chatinho import CredentialUnavailable
    with pytest.raises(CredentialUnavailable):
        await agent.credential(question_id, "llm")
    await session.close()


async def test_a_credential_is_gone_on_timeout():
    agent = Agent(key=False, delay=0.3)
    session, front = await remote(agent, credentials={"llm": "key"})
    async with client(front) as c:
        got = await _lend(c, deadline_ms=100)
    assert got["status"] == "timeout"
    question_id = [m for m in session._context() if m.text == "go"][0].id
    from chatinho import CredentialUnavailable
    with pytest.raises(CredentialUnavailable):
        await agent.credential(question_id, "llm")
    await session.close()


async def test_a_credential_is_never_in_the_conversation():
    agent = Agent(key=True)
    session, front = await remote(agent, credentials={"llm": "key"})
    async with client(front) as c:
        await _lend(c, value="sk-very-secret")
    assert all("sk-very-secret" not in m.text for m in session._context())
    assert "sk-very-secret" not in repr(front._lent({wire.CREDENTIALS_KEY: {"llm": "sk-very-secret"}}))
    await session.close()
