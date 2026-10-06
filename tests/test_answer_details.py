"""Answer statuses on Reply, and ask(..., detail=True)."""

import asyncio

import pytest

from chatinho import (
    Answer,
    Attachment,
    HookAnswer,
    HookKeep,
    HookLink,
    Reply,
    backend,
    connector,
    require,
)
from conftest import driven


@connector("eco")
@require(HookAnswer)
class _Eco:
    def __init__(self, reply):
        self.reply = reply

    async def answer(self, msg):
        return self.reply


@backend("cofre")
@require(HookKeep)
@require(HookLink)
class _Cofre:
    def __init__(self):
        self.kept = {}

    async def keep(self, msg_id, attachments):
        for item in attachments:
            self.kept[(msg_id, item.name)] = item

    async def link(self, msg_id, name):
        return "file:///%s/%s" % (msg_id, name) if (msg_id, name) in self.kept else None


def test_a_reply_is_answered_unless_it_says_otherwise():
    assert Reply("sunny").status == "answered"
    assert Reply("Which login flow?", status="asked").status == "asked"
    assert Reply("the service is down", status="error").status == "error"


def test_an_unknown_status_is_refused():
    with pytest.raises(ValueError):
        Reply("x", status="maybe")


async def test_ask_returns_the_text_by_default():
    session, view = await driven(connectors=[_Eco("sunny")])
    assert await view.ask(view.id_of("eco"), "weather?") == "sunny"
    await session.close()


@pytest.mark.parametrize("reply, status", [
    ("sunny", "answered"),
    (Reply("Which login flow?", status="asked"), "asked"),
    (Reply("the service is down", status="error"), "error"),
])
async def test_detail_carries_the_status(reply, status):
    session, view = await driven(connectors=[_Eco(reply)])
    got = await view.ask(view.id_of("eco"), "q", detail=True)
    assert isinstance(got, Answer)
    assert got.status == status
    assert got.text == (reply if isinstance(reply, str) else reply.text)
    await session.close()


async def test_detail_gives_the_answer_id_that_locates_its_attachment():
    chart = Attachment("chart.svg", "image/svg+xml", b"<svg/>")
    session, view = await driven(connectors=[_Eco(Reply("[chart](chart.svg)", (chart,)))],
                                 backend=_Cofre())
    got = await view.ask(view.id_of("eco"), "draw it", detail=True)
    assert got.status == "answered"
    assert await session.locate(got.msg_id, "chart.svg") is not None
    assert [m.id for m in view.context()][-1] == got.msg_id
    await session.close()


async def test_an_answer_said_late_is_answered():
    @connector("tarde")
    @require(HookAnswer)
    class _Tarde:
        async def answer(self, msg):
            return None

    tarde   = _Tarde()
    session, view = await driven(connectors=[tarde])
    asking  = asyncio.create_task(view.ask(view.id_of("tarde"), "q", detail=True))
    await asyncio.sleep(0.05)
    question = view.context()[-1]
    await session._say_for(tarde.peer_id)("later", reply_to=question.id)
    got = await asking
    assert (got.text, got.status) == ("later", "answered")
    await session.close()
