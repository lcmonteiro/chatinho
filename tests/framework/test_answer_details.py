"""Answer statuses on Reply and on the message, and a say addressed to one peer."""

import asyncio

import pytest

from chatinho import (
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
        self.reply = Reply(reply) if isinstance(reply, str) else reply
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


def test_a_reply_reads_as_what_it_says():
    """An answer reads as its text; anything else says what it is first."""
    assert str(Reply("sunny")) == "sunny"
    assert str(Reply("which city?", status="asked")) == "asked: which city?"
    assert str(Reply("quota exceeded", status="error")) == "error: quota exceeded"


def test_its_repr_is_still_the_dataclasss():
    told = repr(Reply("sunny"))
    assert "text=" in told and "attachments=" in told and "status=" in told


@pytest.mark.parametrize("reply, status", [
    ("sunny", "answered"),
    (Reply("Which login flow?", status="asked"), "asked"),
    (Reply("the service is down", status="error"), "error"),
])
async def test_the_answer_message_carries_the_status(reply, status):
    session, view = await driven(connectors=[_Eco(reply)])
    assert (await view.ask(view.id_of("eco"), "q")).status == status
    assert view.context()[-1].status == status
    await session.close()


async def test_ask_still_returns_the_text():
    session, view = await driven(connectors=[_Eco("sunny")])
    assert (await view.ask(view.id_of("eco"), "weather?")).text == "sunny"
    await session.close()


# === A say addressed to one peer ===================================================


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


@connector("antigo")
@require(HookAnswer)
class _Antigo:
    """Answers with a bare string, which an answer may no longer do."""

    async def answer(self, msg):
        return "sunny"


async def test_an_answer_must_be_a_reply():
    falador = _Falador()
    session, view = await driven(connectors=[_Antigo(), _Eco(), falador])
    with pytest.raises(TypeError):
        await view.ask(view.id_of("antigo"), "rain?")
    said_id = await falador.say("rain?", to=view.id_of("antigo"))
    await _settle()
    reply = view.context()[-1]
    assert (reply.reply_to, reply.status) == (said_id, "error") and "TypeError" in reply.text
    await session.close()


# === What ask returns ===========================================================


async def test_ask_returns_a_question_back_with_its_status():
    eco = _Eco(Reply("which city?", status="asked"))
    session, view = await driven(connectors=[eco])
    assert await view.ask(eco.peer_id, "weather?") == Reply("which city?", status=ReplyStatus.ASKED)
    await session.close()


async def test_ask_returns_an_error_answer_with_its_status():
    """The status tells the asker a failure from an answer; the text alone could not."""
    eco = _Eco(Reply("quota exceeded", status="error"))
    session, view = await driven(connectors=[eco])
    assert await view.ask(eco.peer_id, "weather?") == Reply("quota exceeded", status=ReplyStatus.ERROR)
    errors = [m for m in view.context() if m.status == ReplyStatus.ERROR]
    assert [m.text for m in errors] == ["quota exceeded"]
    await session.close()
