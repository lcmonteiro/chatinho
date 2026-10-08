"""Answer statuses on Reply and on the message, and a say asked of the lone peer that answers."""

import asyncio

import pytest

from chatinho import (
    TOOL,
    HookAnswer,
    HookListen,
    HookSay,
    Reply,
    ReplyStatus,
    connector,
    require,
)
from conftest import driven


@connector("eco")
@require(HookAnswer)
class _Eco:
    def __init__(self, reply="sunny"):
        self.reply = reply
        self.asked = []

    async def answer(self, msg):
        self.asked.append(msg)
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


@connector("falador")
@require(HookSay)
@require(HookListen)
class _Falador:
    """Says things; hears everything."""

    def __init__(self):
        self.heard = []

    async def listen(self, msg):
        self.heard.append(msg)


async def _settle():
    await asyncio.sleep(0.05)


# === Statuses ======================================================================

def test_a_reply_is_answered_unless_it_says_otherwise():
    assert Reply("sunny").status == "answered"
    assert Reply("Which login flow?", status="asked").status == "asked"
    assert Reply("the service is down", status="error").status == "error"


def test_a_status_is_an_enum_and_its_value_is_accepted():
    assert Reply("x", status=ReplyStatus.ASKED).status is ReplyStatus.ASKED
    assert Reply("x", status="asked").status is ReplyStatus.ASKED
    assert ReplyStatus.ERROR == "error"


def test_an_unknown_status_is_refused():
    with pytest.raises(ValueError):
        Reply("x", status="maybe")


@pytest.mark.parametrize("reply, status", [
    ("sunny", "answered"),
    (Reply("Which login flow?", status="asked"), "asked"),
    (Reply("the service is down", status="error"), "error"),
])
async def test_the_answer_message_carries_the_status(reply, status):
    session, view = await driven(connectors=[_Eco(reply)])
    await view.ask(view.id_of("eco"), "q")
    assert view.context()[-1].status == status
    await session.close()


async def test_ask_still_returns_the_text():
    session, view = await driven(connectors=[_Eco("sunny")])
    assert await view.ask(view.id_of("eco"), "weather?") == "sunny"
    await session.close()


# === A say, asked of the lone peer that answers =====================================

async def test_a_say_is_asked_of_the_only_peer_that_answers():
    eco, falador = _Eco("sunny"), _Falador()
    session, view = await driven(connectors=[eco, falador])
    said_id = await falador.say("will it rain?")
    await _settle()
    assert [m.text for m in eco.asked] == ["will it rain?"]
    said  = [m for m in view.context() if m.id == said_id][0]
    reply = view.context()[-1]
    assert said.to == eco.peer_id
    assert (reply.text, reply.reply_to, reply.to) == ("sunny", said_id, falador.peer_id)
    assert said in view.heard                       # listeners still hear it
    await session.close()


async def test_the_user_saying_asks_the_lone_peer():
    eco = _Eco("sunny")
    session, view = await driven(connectors=[eco])
    await view.say("hello")
    await _settle()
    assert [m.text for m in eco.asked] == ["hello"]
    await session.close()


async def test_a_reply_stays_a_broadcast():
    eco, falador = _Eco(), _Falador()
    session, view = await driven(connectors=[eco, falador])
    first = await view.say("hello")
    await _settle()
    await falador.say("me too", reply_to=first)
    await _settle()
    assert [m.text for m in eco.asked] == ["hello"]
    await session.close()


async def test_with_two_peers_that_answer_a_say_is_a_broadcast():
    one, two, falador = _Eco(), _Eco(), _Falador()
    session, view = await driven(connectors=[one, two, falador])
    said_id = await falador.say("anyone?")
    await _settle()
    assert one.asked == two.asked == []
    assert [m for m in view.context() if m.id == said_id][0].is_broadcast
    await session.close()


async def test_the_speaker_and_the_frontend_do_not_count():
    eco = _Eco()
    session, view = await driven(connectors=[eco])
    said_id = await session._say_for(eco.peer_id)("talking to myself")
    await _settle()
    assert eco.asked == [] and view.asked == []
    assert [m for m in view.context() if m.id == said_id][0].is_broadcast
    await session.close()


async def test_what_a_command_writes_is_not_asked():
    eco = _Eco()
    session, view = await driven(connectors=[eco])
    await session._say_for(TOOL)("usage: /help")
    await _settle()
    assert eco.asked == []
    await session.close()


async def test_an_addressed_say_is_asked_of_that_peer():
    one, two, falador = _Eco("sunny"), _Eco("rainy"), _Falador()
    session, view = await driven(connectors=[one, two, falador])
    said_id = await falador.say("will it rain?", to=two.peer_id)
    await _settle()
    assert one.asked == [] and [m.text for m in two.asked] == ["will it rain?"]
    reply = view.context()[-1]
    assert (reply.text, reply.reply_to) == ("rainy", said_id)
    assert [m for m in view.context() if m.id == said_id][0] in view.heard
    await session.close()


async def test_a_say_to_nobody_is_refused():
    falador = _Falador()
    session, view = await driven(connectors=[_Eco(), falador])
    with pytest.raises(ValueError):
        await falador.say("?", to=99)
    with pytest.raises(ValueError):
        await falador.say("?", to=falador.peer_id)
    await session.close()


async def test_a_lone_peer_that_fails_replies_with_an_error():
    eco, falador = _Eco(RuntimeError("boom")), _Falador()
    session, view = await driven(connectors=[eco, falador])
    said_id = await falador.say("will it rain?")
    await _settle()
    reply = view.context()[-1]
    assert (reply.reply_to, reply.status) == (said_id, "error")
    assert "RuntimeError" in reply.text and reply.frm == eco.peer_id
    await session.close()
