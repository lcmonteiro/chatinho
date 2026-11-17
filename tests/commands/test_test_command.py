"""
``/test``: checks the chat is wired up, saying each check as it goes, and answers whoever ran it.
"""

import re
from typing import List

from chatinho import HookInvoke, Invoke, TestCommand, connector, require
from chatinho.message import TOOL

from conftest import driven


@connector("weather")
class Weather:
    """A peer that is only there to be listed."""


@connector("agent")
class Agent:
    """Another peer that is only there to be listed."""


@connector("bot")
@require(HookInvoke)
class Bot:
    """A peer that runs commands."""

    invoke : Invoke


def said_by_the_command(view) -> List[str]:
    """What the command posted, as ``TOOL``, oldest first: its says, then its answer."""
    return [m.text for m in view.context() if m.frm == TOOL]


def in_reach_before(view, text: str) -> int:
    """How many messages the conversation held when *text* was said."""
    return [m.text for m in view.context()].index(text)


# @ac AC-CMD-006.1
async def test_run_by_the_user():
    session, view = await driven(connectors=[Weather(), Agent()], commands=[TestCommand()])
    await view.say("hello")
    assert await view.command("test") == "Checks done, for peer 0."
    await session.close()
    said = said_by_the_command(view)
    assert said[:2] == ["Running checks…", "Peers: agent, weather"]
    assert re.fullmatch(r"Context: \d+ message\(s\) in reach", said[2])
    assert said[2] == "Context: %d message(s) in reach" % in_reach_before(view, said[2])
    assert said[3:] == ["Checks done, for peer 0."]


# @ac AC-CMD-006.2
async def test_run_by_a_peer_with_arguments():
    bot = Bot()
    session, view = await driven(connectors=[bot], commands=[TestCommand()])
    assert bot.peer_id == 1
    assert await bot.invoke("test", "extra words") == "Checks done, for peer 1."
    await session.close()
    said = said_by_the_command(view)
    assert said[:2] == ["Running checks…", "Peers: bot"]
    assert said[-1] == "Checks done, for peer 1."
    assert not any("extra words" in text for text in said)


# @ac AC-CMD-006.3
async def test_no_peers():
    session, view = await driven(commands=[TestCommand()])
    assert await view.command("test") == "Checks done, for peer 0."
    await session.close()
    assert "Peers: none" in said_by_the_command(view)
