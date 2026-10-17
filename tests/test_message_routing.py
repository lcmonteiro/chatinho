"""
Who answers a say that names nobody: the router decides, and writes it into ``to``.

The router is whichever peer declares ``HookRoute``; with none, ``SimpleRouter``
sends a reply to its author and anything else to the lone peer that answers.
"""

import asyncio
import logging
from typing import List, Optional

import pytest

from chatinho import (
    LOCAL,
    TOOL,
    ChatMessage,
    ChatSession,
    HookAnswer,
    HookExecute,
    HookListen,
    HookPeers,
    HookRoute,
    HookSay,
    Peers,
    Reply,
    SimpleRouter,
    connector,
    require,
    tool,
)
from conftest import driven


@connector("eco")
@require(HookAnswer)
class _Eco:
    def __init__(self, reply="sunny"):
        self.reply = Reply(reply) if isinstance(reply, str) else reply
        self.asked : List[ChatMessage] = []

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
        self.heard : List[ChatMessage] = []

    async def listen(self, msg):
        self.heard.append(msg)


@connector("echo")
@require(HookListen)
class _Echo:
    """Hears what the user says to nobody in particular, as the echo examples do."""

    def __init__(self):
        self.heard : List[str] = []

    async def listen(self, msg):
        if msg.to is None and msg.is_local:
            self.heard.append(msg.text)


@tool("upper", "Upper-cases the rest of the line")
@require(HookExecute)
class _Upper:
    async def execute(self, args="", **kwargs):
        return Reply(args.upper())


@require(HookRoute)
class _Fixed:
    """Routes every say to *to*, and counts what it was consulted for."""

    def __init__(self, to: Optional[int]):
        self.to        = to
        self.consulted : List[str] = []

    async def route(self, msg):
        self.consulted.append(msg.text)
        return self.to


async def _settle():
    await asyncio.sleep(0.05)


def _said(view, msg_id) -> ChatMessage:
    return next(m for m in view.context() if m.id == msg_id)


# === A router decides who an unaddressed say is for =================================

async def test_routed_to_one_peer():
    bot, other = _Eco("hello"), _Eco("bye")
    router     = _Fixed(None)
    session, view = await driven(connectors=[bot, other], router=router)
    router.to  = bot.peer_id
    said = await view.say("hi")
    await session.close()
    assert router.consulted == ["hi"]
    assert _said(view, said).to == bot.peer_id
    assert [m.text for m in bot.asked] == ["hi"] and other.asked == []


async def test_routed_to_nobody():
    bot, router = _Eco(), _Fixed(None)
    session, view = await driven(connectors=[bot], router=router)
    said = await view.say("hi")
    await session.close()
    assert _said(view, said).to is None and bot.asked == []


async def test_an_addressed_say_is_not_routed():
    sol, lua = _Eco("sunny"), _Eco("full moon")
    router   = _Fixed(2)
    session, view = await driven(connectors=[sol, lua], router=router)
    await view.say("hi", to=sol.peer_id)
    await session.close()
    assert router.consulted == []
    assert [m.text for m in sol.asked] == ["hi"] and lua.asked == []


async def test_a_commands_output_is_not_routed():
    router = _Fixed(1)
    session, view = await driven(connectors=[_Eco()], commands=[_Upper()], router=router)
    await view.command("upper", "shout")
    await session.close()
    assert router.consulted == []


async def test_what_a_command_writes_is_not_routed():
    eco = _Eco()
    session, view = await driven(connectors=[eco])
    said = await session._say_for(TOOL)("usage: /help")
    await session.close()
    assert eco.asked == [] and _said(view, said).to is None


# === The router is the one router= was given ======================================

async def test_declaring_hookroute_does_not_make_a_connector_the_router():
    @connector("triage")
    @require(HookAnswer)
    @require(HookRoute)
    class Triage:
        def __init__(self):
            self.answered : List[str] = []

        async def route(self, msg):
            return getattr(self, "peer_id")

        async def answer(self, msg):
            self.answered.append(msg.text)
            return Reply("triaged")

    triage = Triage()
    session, view = await driven(connectors=[triage, _Eco(), _Eco()])
    said = await view.say("hi")
    await session.close()
    assert _said(view, said).to is None and triage.answered == []


async def test_a_router_reads_the_room():
    @connector("reader")
    @require(HookRoute)
    @require(HookPeers)
    class Reader:
        peers : Peers

        async def route(self, msg):
            return next((at for at, who in self.peers().items() if getattr(who, "name", "") == "eco"), None)

    reader, eco = Reader(), _Eco()
    session, view = await driven(connectors=[eco, _Eco("other")], router=reader)
    said = await view.say("hi")
    await session.close()
    assert reader not in view.peers().values() and not hasattr(reader, "peer_id")
    assert _said(view, said).to == eco.peer_id


async def test_a_router_starts_and_stops_with_the_chat():
    @require(HookRoute)
    class Lived:
        def __init__(self):
            self.life : List[str] = []

        async def initialize(self):
            self.life.append("up")

        async def shutdown(self):
            self.life.append("down")

        async def route(self, msg):
            return None

    lived = Lived()
    session, _ = await driven(router=lived)
    await session.close()
    assert lived.life == ["up", "down"]


def test_a_router_must_declare_hookroute():
    with pytest.raises(TypeError):
        ChatSession(router=_Eco())


async def test_without_a_router_nothing_is_routed():
    eco = _Eco()
    session, view = await driven(connectors=[eco], router=None)
    said = await view.say("hi")
    await session.close()
    assert _said(view, said).to is None and eco.asked == []


# === What a router returns is checked ===============================================

@pytest.mark.parametrize("pick", ["speaker", "listener", "stranger"])
async def test_a_bad_route_is_ignored(pick, caplog):
    eco, falador = _Eco(), _Falador()
    router = _Fixed(None)
    session, view = await driven(connectors=[eco, falador], router=router)
    router.to = {"speaker": LOCAL, "listener": falador.peer_id, "stranger": 99}[pick]
    with caplog.at_level(logging.WARNING, logger="chatinho.session"):
        said = await view.say("hi")
        await session.close()
    assert _said(view, said).to is None and eco.asked == []
    assert "Ignored the router's" in caplog.text


async def test_a_failing_router_does_not_stop_the_say(caplog):
    @require(HookRoute)
    class Broken:
        async def route(self, msg):
            raise RuntimeError("no idea")

    eco = _Eco()
    session, view = await driven(connectors=[eco], router=Broken())
    with caplog.at_level(logging.ERROR, logger="chatinho.session"):
        said = await view.say("hi")
        await session.close()
    assert _said(view, said).to is None and eco.asked == []
    assert "Routing" in caplog.text and "no idea" in caplog.text


# === The default router =============================================================

async def test_one_peer_answers():
    eco, falador = _Eco("sunny"), _Falador()
    session, view = await driven(connectors=[eco, falador])
    said = await falador.say("will it rain?")
    await _settle()
    assert [m.text for m in eco.asked] == ["will it rain?"]
    reply = view.context()[-1]
    assert _said(view, said).to == eco.peer_id
    assert (reply.text, reply.reply_to, reply.to) == ("sunny", said, None)
    assert _said(view, said) in view.heard                       # listeners still hear it
    await session.close()


async def test_several_peers_answer():
    one, two, falador = _Eco(), _Eco(), _Falador()
    session, view = await driven(connectors=[one, two, falador])
    said = await falador.say("anyone?")
    await _settle()
    assert one.asked == two.asked == []
    assert _said(view, said).to is None
    await session.close()


async def test_the_speaker_and_the_frontend_do_not_count():
    eco = _Eco()
    session, view = await driven(connectors=[eco])
    said = await session._say_for(eco.peer_id)("talking to myself")
    await _settle()
    assert eco.asked == [] and view.asked == []
    assert _said(view, said).to is None
    await session.close()


async def test_a_reply_to_the_user_goes_to_nobody():
    """A reply to what the user said is put neither to the user nor to the lone peer."""
    eco, falador = _Eco(), _Falador()
    session, view = await driven(connectors=[eco, falador])
    first = await view.say("hello")
    await _settle()
    await falador.say("me too", reply_to=first)
    await _settle()
    assert [m.text for m in eco.asked] == ["hello"]
    await session.close()


async def _answer_of(view, eco, text):
    """Says *text* as the user and returns the id of *eco*'s answer to it."""
    said = await view.say(text)
    await _settle()
    return [m for m in view.context() if m.reply_to == said and m.frm == eco.peer_id][0].id


async def test_the_user_follows_up_on_an_answer():
    bot = _Eco("sunny")
    session, view = await driven(connectors=[bot])
    answer   = await _answer_of(view, bot, "hello")
    followed = await view.say("and tomorrow?", reply_to=answer)
    await _settle()
    assert [m.text for m in bot.asked] == ["hello", "and tomorrow?"]
    assert _said(view, followed).to == bot.peer_id
    reply = view.context()[-1]
    assert (reply.frm, reply.reply_to) == (bot.peer_id, followed)
    await session.close()


async def test_following_up_in_a_room_with_several_peers():
    sol, lua = _Eco("sunny"), _Eco("full moon")
    session, view = await driven(connectors=[sol, lua])
    asked = await view.say("will it rain?", to=sol.peer_id)
    await _settle()
    answer   = [m for m in view.context() if m.reply_to == asked][0].id
    followed = await view.say("and tomorrow?", reply_to=answer)
    await _settle()
    assert [m.text for m in sol.asked] == ["will it rain?", "and tomorrow?"]
    assert lua.asked == [] and _said(view, followed).to == sol.peer_id
    await session.close()


async def test_replying_to_a_peer_that_does_not_answer():
    eco, falador = _Eco(), _Falador()
    session, view = await driven(connectors=[eco, falador])
    first = await falador.say("anyone?", to=view.peer_id)
    await _settle()
    reply = await view.say("me", reply_to=first)
    await _settle()
    assert eco.asked == [] and _said(view, reply).to is None
    await session.close()


async def test_replying_to_a_commands_output():
    eco = _Eco()
    session, view = await driven(connectors=[eco], commands=[_Upper()])
    await view.command("upper", "shout")
    output = view.context()[-1]
    assert output.frm == TOOL
    reply = await view.say("thanks", reply_to=output.id)
    await _settle()
    assert eco.asked == [] and _said(view, reply).to is None
    await session.close()


async def test_an_explicit_recipient_wins():
    sol, lua = _Eco("sunny"), _Eco("full moon")
    session, view = await driven(connectors=[sol, lua])
    asked = await view.say("will it rain?", to=sol.peer_id)
    await _settle()
    answer = [m for m in view.context() if m.reply_to == asked][0].id
    await view.say("and you?", to=lua.peer_id, reply_to=answer)
    await _settle()
    assert [m.text for m in sol.asked] == ["will it rain?"]
    assert [m.text for m in lua.asked] == ["and you?"]
    await session.close()


async def test_replying_to_oneself():
    eco = _Eco()
    session, view = await driven(connectors=[eco])
    say  = session._say_for(eco.peer_id)
    mine = await say("a thought")
    await _settle()
    reply = await say("and another", reply_to=mine)
    await _settle()
    assert _said(view, reply).to is None
    await session.close()


async def test_a_lone_peer_that_fails_replies_with_an_error():
    eco, falador = _Eco(RuntimeError("boom")), _Falador()
    session, view = await driven(connectors=[eco, falador])
    said = await falador.say("will it rain?")
    await _settle()
    reply = view.context()[-1]
    assert (reply.reply_to, reply.status) == (said, "error")
    assert "RuntimeError" in reply.text and reply.frm == eco.peer_id
    await session.close()


async def test_a_listener_of_unaddressed_says_stays_quiet_when_the_say_is_routed():
    """The cost the proposal names: routed, the say is no longer owed by nobody."""
    bot, echo = _Eco("hello"), _Echo()
    session, view = await driven(connectors=[bot, echo])
    said = await view.say("hi")
    await session.close()
    assert _said(view, said).to == bot.peer_id
    assert [m.text for m in bot.asked] == ["hi"] and echo.heard == []


# === An answer is addressed to nobody ===============================================

async def test_a_command_is_answered_by_nobody():
    session, view = await driven(connectors=[_Eco()], commands=[_Upper()])
    await view.command("upper", "shout")
    invocation, result = view.context()[-2:]
    assert invocation.to == TOOL and result.to is None
    await session.close()


async def test_a_late_answer_is_not_routed():
    @connector("late")
    @require(HookAnswer)
    @require(HookSay)
    class Late:
        async def answer(self, msg):
            await self.say("later", reply_to=msg.id)
            return None

    router = _Fixed(None)
    late   = Late()
    session, view = await driven(connectors=[late], router=router)
    assert (await asyncio.wait_for(view.ask(late.peer_id, "when?"), timeout=2)).text == "later"
    await session.close()
    assert router.consulted == []


async def test_the_builders_route_with_simple_router_unless_given_one():
    pytest.importorskip("textual")
    pytest.importorskip("fastmcp")
    from chatinho import build_chat_session, build_mcp_session
    for build, extra in ((build_chat_session, {}), (build_mcp_session, {"token": "t"})):
        assert isinstance(build(**extra).router, SimpleRouter)
        mine = _Fixed(None)
        assert build(router=mine, **extra).router is mine
