"""McpConnector: putting questions to a remote session from the local chat."""

import asyncio

import pytest

from chatinho import Attachment, HookAnswer, Reply, connector, require
from chatinho.connectors.mcp import McpConnector
from conftest import driven
from mcp_kit import Agent, Files, Weather, remote


async def _local(connector, **kwargs):
    """A local chat with the connector in it."""
    return await driven(connectors=[connector], **kwargs)


@connector("quiet")
@require(HookAnswer)
class _Quiet:
    """A second local peer that answers, so what the user says stays a broadcast, asked of nobody."""

    async def answer(self, msg):
        return None


async def _asked(view, lab, text):
    """Asks the connector directly and returns its reply message, status included."""
    await view.ask(lab.peer_id, text)
    return view.context()[-1]


async def _replies(view, count: int, timeout: float = 5.0):
    """Waits until the local chat holds *count* messages, and returns them."""
    for _ in range(int(timeout / 0.02)):
        if len(view.context()) >= count:
            break
        await asyncio.sleep(0.02)
    return view.context()


def test_exactly_one_server():
    with pytest.raises(ValueError):
        McpConnector()
    with pytest.raises(ValueError):
        McpConnector(server=object(), url="https://y", token="t")
    with pytest.raises(ValueError):
        McpConnector(url="https://lab.example/mcp")          # no token


# === Naming ========================================================================

async def test_named_by_the_connector():
    remote_session, front = await remote(Weather())
    lab = McpConnector(server=front.server, name="lab")
    session, view = await _local(lab)
    assert lab.name == "lab"
    assert await view.ask(lab.peer_id, "rain?") == "sunny"
    await session.close()
    await remote_session.close()


async def test_named_by_the_server_when_not_given():
    remote_session, front = await remote(Weather(), name="office")
    office = McpConnector(server=front.server)
    session, view = await _local(office)
    assert office.name == "office"
    await view.say("@office rain?")
    texts = [m.text for m in await _replies(view, 2)]
    assert texts[-1] == "sunny"
    await session.close()
    await remote_session.close()


# === Being asked ==================================================================

@pytest.mark.parametrize("said", ["@lab will it rain?", "will it rain?"])
async def test_what_is_said_to_the_room_is_not_taken(said):
    weather = Weather()
    remote_session, front = await remote(weather)
    session, view = await driven(connectors=[McpConnector(server=front.server, name="lab"), _Quiet()])
    await view.say(said)
    await asyncio.sleep(0.2)
    assert weather.asked == [] and len(view.context()) == 1
    await session.close()
    await remote_session.close()


async def test_the_only_peer_here_gets_everything_said():
    weather = Weather()
    remote_session, front = await remote(weather)
    session, view = await _local(McpConnector(server=front.server, name="lab"))
    await view.say("will it rain?")
    await _replies(view, 2)
    assert [m.text for m in weather.asked] == ["will it rain?"]
    await session.close()
    await remote_session.close()


async def test_asked_directly():
    remote_session, front = await remote(Weather("sunny"))
    lab = McpConnector(server=front.server, name="lab")
    session, view = await _local(lab)
    assert await view.ask(lab.peer_id, "rain?") == "sunny"
    assert await view.ask(lab.peer_id, "@lab rain?") == "sunny"
    await session.close()
    await remote_session.close()


# === One reply per question ========================================================

async def test_an_answer_with_an_attachment_is_kept_here(tmp_path):
    chart = Attachment("chart.svg", "image/svg+xml", b"<svg/>")
    remote_session, front = await remote(Agent(attach=chart), backend=Files(tmp_path / "there"))
    here = Files(tmp_path / "here")
    session, view = await _local(McpConnector(server=front.server, name="lab"), backend=here)
    await view.say("@lab draw it")
    reply = (await _replies(view, 2))[-1]
    assert "[chart](chart.svg)" in reply.text
    assert (tmp_path / "here" / str(reply.id) / "chart.svg").read_bytes() == b"<svg/>"
    await session.close()
    await remote_session.close()


async def test_a_question_back_is_marked():
    remote_session, front = await remote(Weather(Reply("which city?", status="asked")))
    lab = McpConnector(server=front.server, name="lab")
    session, view = await _local(lab)
    got = await _asked(view, lab, "rain?")
    assert (got.status, got.text) == ("asked", "lab asks: which city?")
    await session.close()
    await remote_session.close()


async def test_no_remote_peer_is_said_briefly():
    remote_session, front = await remote()
    lab = McpConnector(server=front.server, name="lab")
    session, view = await _local(lab)
    got = await _asked(view, lab, "rain?")
    assert got.status == "error" and got.text.startswith("lab: no single remote peer answers")
    await session.close()
    await remote_session.close()


async def test_an_unreachable_server_still_gets_a_reply():
    lab = McpConnector(url="http://127.0.0.1:9/mcp", token="t", name="lab")
    session, view = await _local(lab)
    await view.say("@lab anyone?")
    reply = (await _replies(view, 2))[-1]
    assert reply.text.startswith("lab: could not reach the remote session")
    await session.close()


# === Lending credentials ===========================================================

async def test_a_credential_is_sent_with_the_question():
    agent = Agent(key=True)
    remote_session, front = await remote(agent, credentials={"llm": "key"})
    lab = McpConnector(server=front.server, name="lab", delegate={"llm": "sk-test"})
    session, view = await _local(lab)
    await view.ask(lab.peer_id, "go")
    assert agent.keys == ["sk-test"]
    assert all("sk-test" not in m.text for m in remote_session._context() + view.context())
    await session.close()
    await remote_session.close()


async def test_not_declared_not_sent():
    agent = Agent(key=True)
    remote_session, front = await remote(agent)
    lab = McpConnector(server=front.server, name="lab", delegate={"llm": "sk-test"})
    session, view = await _local(lab)
    await view.ask(lab.peer_id, "go")
    assert agent.keys == [None]
    assert lab._lending(lab._client) is None
    await session.close()
    await remote_session.close()


async def test_plain_http_is_refused():
    lab = McpConnector(url="http://lab.example:8000/mcp", token="t", name="lab", delegate={"llm": "sk"})
    session, view = await _local(lab)
    got = await _asked(view, lab, "go")
    assert got.status == "error" and "HTTPS" in got.text
    await session.close()


def test_https_and_this_machine_may_lend():
    for url in ("https://lab.example/mcp", "http://127.0.0.1:8000/mcp", "http://localhost:8000/mcp"):
        assert McpConnector(url=url, token="t", delegate={"llm": "sk"})._may_delegate()


async def test_a_token_per_question():
    minted = []

    def mint():
        minted.append("tok-%d" % len(minted))
        return minted[-1]

    agent = Agent(key=True)
    remote_session, front = await remote(agent, credentials={"llm": "key"})
    lab = McpConnector(server=front.server, name="lab", delegate={"llm": mint})
    session, view = await _local(lab)
    await view.ask(lab.peer_id, "one")
    await view.ask(lab.peer_id, "two")
    assert agent.keys == ["tok-0", "tok-1"] == minted
    await session.close()
    await remote_session.close()


async def test_nothing_is_lent_without_delegate():
    agent = Agent(key=True)
    remote_session, front = await remote(agent, credentials={"llm": "key"})
    lab = McpConnector(server=front.server, name="lab")
    session, view = await _local(lab)
    await view.ask(lab.peer_id, "go")
    assert agent.keys == [None]
    assert lab._lending(lab._client) is None
    await session.close()
    await remote_session.close()


async def test_no_link_stays_open_between_questions():
    remote_session, front = await remote(Weather())
    lab = McpConnector(server=front.server, name="lab")
    session, view = await _local(lab)
    assert await view.ask(lab.peer_id, "rain?") == "sunny"
    assert not lab._client.is_connected()
    await session.close()
    await remote_session.close()


async def test_two_questions_at_once():
    remote_session, front = await remote(Weather("sunny", delay=0.2))
    lab = McpConnector(server=front.server, name="lab")
    session, view = await _local(lab)
    got = await asyncio.gather(view.ask(lab.peer_id, "one?"), view.ask(lab.peer_id, "two?"))
    assert got == ["sunny", "sunny"]
    await session.close()
    await remote_session.close()


async def test_with_several_remote_peers_one_is_named():
    weather = Weather("sunny")
    remote_session, front = await remote(Agent(), weather)
    unnamed = McpConnector(server=front.server, name="lab")
    named   = McpConnector(server=front.server, name="sky", peer="weather")
    session, view = await driven(connectors=[unnamed, named])
    got = await _asked(view, unnamed, "rain?")
    assert got.status == "error" and "peer=" in got.text
    assert await view.ask(named.peer_id, "rain?") == "sunny"
    assert [m.text for m in weather.asked] == ["rain?"]
    await session.close()
    await remote_session.close()


async def test_a_remote_error_is_said_briefly():
    remote_session, front = await remote(Weather(Reply("the service is down", status="error")))
    lab = McpConnector(server=front.server, name="lab")
    session, view = await _local(lab)
    got = await _asked(view, lab, "rain?")
    assert got.status == "error" and got.text == "lab: error — the service is down"
    await session.close()
    await remote_session.close()
