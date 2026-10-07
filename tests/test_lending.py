"""Credentials ride on the message, for whoever answers it."""

import asyncio

from chatinho import HookAnswer, HookSay, Secret, connector, require
from conftest import driven


@connector("pensador")
@require(HookAnswer)
class _Pensador:
    """Remembers the key each message brought."""

    def __init__(self):
        self.keys = []

    async def answer(self, msg):
        lent = msg.credentials.get("llm")
        self.keys.append(lent.reveal() if lent is not None else None)
        return "ok"


@connector("lender")
@require(HookSay)
class _Lender:
    pass


async def test_each_message_brings_its_own_key():
    peer, lender = _Pensador(), _Lender()
    session, _ = await driven(connectors=[peer, lender])
    await lender.say("one", credentials={"llm": Secret("sk-one")})
    await lender.say("two", credentials={"llm": Secret("sk-two")})
    await lender.say("three")
    await asyncio.sleep(0.05)
    assert peer.keys == ["sk-one", "sk-two", None]
    await session.close()


async def test_the_message_keeps_the_lenders_mapping_so_it_can_be_cleared():
    peer, lender = _Pensador(), _Lender()
    session, view = await driven(connectors=[peer, lender])
    lent = {"llm": Secret("sk-one")}
    said = await lender.say("one", credentials=lent)
    await asyncio.sleep(0.05)
    lent.clear()
    msg = [m for m in view.context() if m.id == said][0]
    assert msg.credentials == {}
    await session.close()


async def test_a_key_never_shows():
    peer, lender = _Pensador(), _Lender()
    session, view = await driven(connectors=[peer, lender])
    said = await lender.say("one", credentials={"llm": Secret("sk-hidden")})
    await asyncio.sleep(0.05)
    msg = [m for m in view.context() if m.id == said][0]
    assert "sk-hidden" not in repr(msg) and "sk-hidden" not in msg.text
    await session.close()


def test_a_secret_never_shows_itself():
    secret = Secret("sk-test")
    assert "sk-test" not in repr(secret) and "sk-test" not in str(secret)
    assert "sk-test" not in "%s %r" % (secret, secret)
    assert secret.reveal() == "sk-test"
