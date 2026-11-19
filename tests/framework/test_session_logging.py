"""
Tests for what the session logs of a chat: every event, by ids and counts, and never what was said.
"""

import logging
from typing import List, Optional

import pytest

from chatinho import (
    Attachment,
    ChatMessage,
    HookAnswer,
    HookExecute,
    HookKeep,
    HookListen,
    LOCAL,
    Reply,
    Secret,
    connector,
    require,
    tool,
)
from conftest import driven


@pytest.fixture(autouse=True)
def everything(caplog):
    caplog.set_level(logging.DEBUG, logger="chatinho")
    return caplog


def said(caplog) -> List[str]:
    return [r.getMessage() for r in caplog.records if r.name.startswith("chatinho")]


def having(caplog, *words: str) -> List[str]:
    return [m for m in said(caplog) if all(w in m for w in words)]


@connector("bot")
@require(HookAnswer)
class Bot:
    def __init__(self, answer: str = "ok", fails: bool = False) -> None:
        self.reply = answer
        self.fails = fails

    async def answer(self, msg: ChatMessage) -> Optional[Reply]:
        if self.fails:
            raise RuntimeError("broken while answering")
        return Reply(self.reply)


@tool("upper", "Upper-case the rest of the line")
@require(HookExecute)
class Upper:
    async def execute(self, args: str = "", by: int = LOCAL, **kwargs) -> Reply:
        return Reply(args.upper())


@connector("archive")
@require(HookListen)
@require(HookKeep)
class Keeper:
    async def listen(self, msg: ChatMessage) -> None:
        pass

    async def keep(self, msg_id, attachments) -> None:
        pass


# @ac AC-CORE-035.1
async def test_attached_started_and_closed_are_logged(caplog):
    session, view = await driven(connectors=[Bot()], commands=[Upper()])
    bot = view.id_of("bot")
    await session.close()
    assert having(caplog, "attached", "bot", str(bot))
    assert having(caplog, "attached", "upper")
    assert having(caplog, "started", "loaded 0")
    assert having(caplog, "closed")


# @ac AC-CORE-035.2
async def test_a_message_posted_is_logged_by_its_ids(caplog):
    session, view = await driven()
    first  = await view.say("first words")
    second = await view.say("a reply of 24 characters", reply_to=first)
    await session.close()
    found = having(caplog, "posted", str(second))
    assert found
    line = found[0]
    assert str(first) in line
    assert str(LOCAL) in line
    assert "answered" in line                                 # its status
    assert "24" in line                                       # its length, not its text


# @ac AC-CORE-035.3
async def test_an_ask_and_its_answer_are_logged(caplog):
    session, view = await driven(connectors=[Bot()])
    reply = await view.ask(view.id_of("bot"), "a question")
    await session.close()
    assert reply.text == "ok"
    question = next(m for m in view.context() if m.text == "a question")
    assert having(caplog, "answered", str(question.id), "answered")


# @ac AC-CORE-035.4
async def test_an_ask_that_fails_is_logged_with_its_traceback(caplog):
    session, view = await driven(connectors=[Bot(fails=True)])
    await view.ask(view.id_of("bot"), "a question")
    await session.close()
    question = next(m for m in view.context() if m.text == "a question")
    errors = [r for r in caplog.records if r.levelno >= logging.ERROR and r.exc_info]
    assert errors
    assert having(caplog, "answered", str(question.id), "error")


# @ac AC-CORE-035.5
async def test_a_command_run_is_logged_with_who_ran_it(caplog):
    session, view = await driven(commands=[Upper()])
    await view.command("upper", "loud")
    await session.close()
    assert having(caplog, "ran", "upper", "by %d" % LOCAL)


# @ac AC-CORE-035.6
async def test_a_routing_decision_is_logged(caplog):
    session, view = await driven(connectors=[Bot()])
    msg = await view.say("for whoever answers")
    await session.close()
    assert having(caplog, "routed", str(msg), str(view.id_of("bot")))


# @ac AC-CORE-035.7
async def test_forgetting_is_logged_with_how_many_went(caplog):
    session, view = await driven()
    for n in range(3):
        await view.say("message %d" % n)
    gone = await session.forget()
    await session.close()
    assert gone == 3
    assert having(caplog, "forgot", "3")


# @ac AC-CORE-036.1
async def test_nothing_said_and_no_credential_reaches_the_log(caplog):
    session, view = await driven(connectors=[Bot("FOURTH-answer-zebra"), Keeper()])
    await view.say("FIRST-said-zebra", credentials={"llm": Secret("sk-SECRET-zebra")})
    await view.ask(view.id_of("bot"), "SECOND-asked-zebra",
                   attachments=[Attachment("note.txt", "text/plain", b"THIRD-attached-zebra")])
    await session.close()
    every = "\n".join(said(caplog)) + "\n".join(r.getMessage() for r in caplog.records)
    for text in ("FIRST-said-zebra", "SECOND-asked-zebra", "THIRD-attached-zebra",
                 "FOURTH-answer-zebra", "sk-SECRET-zebra"):
        assert text not in every, text
    assert having(caplog, "posted")                   # there were records to look in


# @ac AC-CORE-036.2
async def test_a_failure_is_logged_with_its_traceback_and_not_the_question(caplog):
    session, view = await driven(connectors=[Bot(fails=True)])
    await view.ask(view.id_of("bot"), "QUESTION-zebra")
    await session.close()
    errors = [r for r in caplog.records if r.levelno >= logging.ERROR and r.exc_info]
    assert errors
    assert any(r.exc_info[0] is RuntimeError for r in errors)
    assert not any("QUESTION-zebra" in r.getMessage() for r in caplog.records)
