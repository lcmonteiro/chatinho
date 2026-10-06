"""Peers joining and leaving a running session."""

import asyncio

import pytest

from chatinho import LOCAL, HookAnswer, HookListen, PeerRemoved, connector, require
from conftest import driven


@connector("ouvinte")
@require(HookListen)
class _Ouvinte:
    def __init__(self):
        self.heard = []
        self.down  = False

    async def listen(self, msg):
        self.heard.append(msg.text)

    def shutdown(self):
        self.down = True


@connector("mudo")
@require(HookAnswer)
class _Mudo:
    async def answer(self, msg):
        return None


async def test_a_peer_added_after_start_takes_part():
    session, view = await driven()
    late = _Ouvinte()
    session.add_connector(late)
    await session.start()
    await view.say("hello")
    await asyncio.sleep(0.05)
    assert late.heard == ["hello"]
    await session.close()


async def test_a_removed_peer_hears_nothing_more():
    ouvinte = _Ouvinte()
    session, view = await driven(connectors=[ouvinte])
    session.remove_connector(ouvinte.peer_id)
    await view.say("anyone?")
    await asyncio.sleep(0.05)
    assert ouvinte.heard == []
    assert ouvinte.peer_id not in view.peers()
    assert ouvinte.down
    await session.close()


async def test_a_waiting_question_fails_when_its_peer_leaves():
    mudo = _Mudo()
    session, view = await driven(connectors=[mudo])
    asking = asyncio.create_task(view.ask(mudo.peer_id, "hello?"))
    await asyncio.sleep(0.05)
    session.remove_connector(mudo.peer_id)
    with pytest.raises(PeerRemoved):
        await asyncio.wait_for(asking, 1)
    await session.close()


async def test_what_a_removed_peer_said_stays():
    ouvinte = _Ouvinte()
    session, view = await driven(connectors=[ouvinte])
    said = session._say_for(ouvinte.peer_id)
    await said("I was here")
    session.remove_connector(ouvinte.peer_id)
    kept = [m for m in view.context() if m.text == "I was here"]
    assert kept and kept[0].frm == ouvinte.peer_id
    await session.close()


async def test_the_frontend_and_strangers_cannot_be_removed():
    session, view = await driven()
    with pytest.raises(ValueError):
        session.remove_connector(LOCAL)
    with pytest.raises(ValueError):
        session.remove_connector(99)
    assert LOCAL in view.peers()
    await session.close()
