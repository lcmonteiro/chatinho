"""Answer statuses on Reply and on the message, and a say asked of the lone peer that answers."""

import asyncio

import pytest

from chatinho import (
    TOOL,
    HookAnswer,
    HookExecute,
    HookListen,
    HookSay,
    Reply,
    ReplyStatus,
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


# === A say, asked of the lone peer that answers =====================================

async def test_a_say_is_asked_of_the_only_peer_that_answers():
    eco, falador = _Eco("sunny"), _Falador()
    session, view = await driven(connectors=[eco, falador])
    said_id = await falador.say("will it rain?")
    await _settle()
    assert [m.text for m in eco.asked] == ["will it rain?"]
    said  = [m for m in view.context() if m.id == said_id][0]
    reply = view.context()[-1]
    assert (said.to, said.asked_of) == (None, eco.peer_id)
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
    """A reply to what the user said is not put to the user, nor to the lone peer."""
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
    said = [m for m in view.context() if m.id == said_id][0]
    assert said.is_broadcast and said.asked_of is None
    await session.close()


async def test_the_speaker_and_the_frontend_do_not_count():
    eco = _Eco()
    session, view = await driven(connectors=[eco])
    said_id = await session._say_for(eco.peer_id)("talking to myself")
    await _settle()
    assert eco.asked == [] and view.asked == []
    said = [m for m in view.context() if m.id == said_id][0]
    assert said.is_broadcast and said.asked_of is None
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


# === A reply, asked of the peer it replies to =======================================

@tool("upper", "Upper-cases the rest of the line")
@require(HookExecute)
class _Upper:
    async def execute(self, args="", **kwargs):
        return Reply(args.upper())


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
    reply = view.context()[-1]
    assert (reply.frm, reply.reply_to) == (bot.peer_id, followed)
    await session.close()


async def test_following_up_in_a_room_with_several_peers():
    sol, lua = _Eco("sunny"), _Eco("full moon")
    session, view = await driven(connectors=[sol, lua])
    asked = await view.say("will it rain?", to=sol.peer_id)
    await _settle()
    answer = [m for m in view.context() if m.reply_to == asked][0].id
    await view.say("and tomorrow?", reply_to=answer)
    await _settle()
    assert [m.text for m in sol.asked] == ["will it rain?", "and tomorrow?"]
    assert lua.asked == []
    await session.close()


async def test_replying_to_a_peer_that_does_not_answer():
    eco, falador = _Eco(), _Falador()
    session, view = await driven(connectors=[eco, falador])
    first = await falador.say("anyone?", to=view.peer_id)
    await _settle()
    reply = await view.say("me", reply_to=first)
    await _settle()
    assert eco.asked == []
    said = [m for m in view.context() if m.id == reply][0]
    assert said.is_broadcast and said.asked_of is None
    await session.close()


async def test_replying_to_a_commands_output():
    eco = _Eco()
    session, view = await driven(connectors=[eco], commands=[_Upper()])
    await view.command("upper", "shout")
    output = view.context()[-1]
    assert output.frm == TOOL
    reply = await view.say("thanks", reply_to=output.id)
    await _settle()
    assert eco.asked == []
    said = [m for m in view.context() if m.id == reply][0]
    assert said.is_broadcast and said.asked_of is None
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
    said = [m for m in view.context() if m.id == reply][0]
    assert said.is_broadcast and said.asked_of is None
    await session.close()


# === Said to, asked of =============================================================

@connector("echo")
@require(HookListen)
class _Echo:
    """Hears what the user says to the room, as the echo examples do, and nothing else."""

    def __init__(self):
        self.heard = []

    async def listen(self, msg):
        if msg.is_broadcast and msg.is_local:
            self.heard.append(msg.text)


async def test_routed_and_still_said_to_the_room():
    bot, echo = _Eco("hello"), _Echo()
    session, view = await driven(connectors=[bot, echo])
    said_id = await view.say("hi")
    await session.close()
    said = [m for m in view.context() if m.id == said_id][0]
    assert (said.to, said.asked_of) == (None, bot.peer_id)
    assert [m.text for m in bot.asked] == ["hi"]
    assert echo.heard == ["hi"]


async def test_asked_directly_is_asked_of_that_peer():
    sol = _Eco("sunny")
    session, view = await driven(connectors=[sol])
    await view.ask(sol.peer_id, "rain?")
    question, answer = view.context()[-2:]
    assert (question.to, question.asked_of) == (sol.peer_id, sol.peer_id)
    assert (answer.to, answer.asked_of) == (view.peer_id, None)
    await session.close()


async def test_a_command_is_asked_of_nobody():
    session, view = await driven(connectors=[_Eco()], commands=[_Upper()])
    await view.command("upper", "shout")
    invocation, result = view.context()[-2:]
    assert (invocation.to, invocation.asked_of) == (TOOL, None)
    assert result.asked_of is None
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
