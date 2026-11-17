"""
Tests for the peer suggestions: a leading ``@`` lists the peers that can be asked.

The same popup lists commands after ``/``; here it is fed the roster, and only
the peers that answer are offered — never the terminal, never a peer that only
listens.
"""

from typing import List, Tuple

from textual.widgets import OptionList

from chatinho import ChatSession, HookAnswer, HookListen, Reply, connector, require
from chatinho.frontends.chat import ChatFrontend
from chatinho.frontends.chat.composer import CommandInput
from chatinho.routers import SimpleRouter


def answering(name: str):
    """A peer that answers, and remembers what it was asked."""
    @connector(name)
    @require(HookAnswer)
    class _Answering:
        def __init__(self) -> None:
            self.asked : List[str] = []

        async def answer(self, msg) -> Reply:
            self.asked.append(msg.text)
            return Reply("ok")
    return _Answering()


def listening(name: str):
    """A peer that only listens: there is nothing to ask it."""
    @connector(name)
    @require(HookListen)
    class _Listening:
        async def listen(self, msg) -> None:
            return None
    return _Listening()


async def chat_frontend(connectors=None) -> Tuple[ChatSession, ChatFrontend]:
    """The terminal attached to a session, as build_chat_session does it, with the session kept."""
    session = ChatSession(connectors=connectors, router=SimpleRouter())
    app = ChatFrontend()
    session.add_connector(app)
    await session.start()
    return session, app


def offered(app: ChatFrontend) -> set:
    """What the popup offers right now."""
    return {o.id for o in app.query_one("#suggestions", OptionList).options}


def visible(app: ChatFrontend) -> bool:
    """Whether the popup is showing."""
    return app.query_one("#suggestions", OptionList).has_class("-visible")


# @ac AC-FRONT-029.1
async def test_ac_front_029_1_at_alone_lists_every_answering_peer():
    session, app = await chat_frontend([answering("sol"), answering("lua")])
    async with app.run_test() as pilot:
        await pilot.press("@")
        assert visible(app)
        assert offered(app) == {"@sol", "@lua"}
        assert "@" + app.name not in offered(app)
    await session.close()


# @ac AC-FRONT-029.2
async def test_ac_front_029_2_a_peer_that_does_not_answer_is_not_listed():
    session, app = await chat_frontend([answering("sol"), listening("arquivo")])
    async with app.run_test() as pilot:
        await pilot.press("@")
        assert offered(app) == {"@sol"}
    await session.close()


# @ac AC-FRONT-029.3
async def test_ac_front_029_3_typing_filters_peers_by_prefix():
    session, app = await chat_frontend([answering("sol"), answering("sombra"), answering("lua")])
    async with app.run_test() as pilot:
        await pilot.press("@", "s", "o")
        assert offered(app) == {"@sol", "@sombra"}
        await pilot.press("m")
        assert offered(app) == {"@sombra"}
    await session.close()


# @ac AC-FRONT-029.4
async def test_ac_front_029_4_no_match_hides_the_list():
    session, app = await chat_frontend([answering("sol")])
    async with app.run_test() as pilot:
        await pilot.press("@")
        assert visible(app)
        await pilot.press("z")
        assert not visible(app)
        assert offered(app) == set()
    await session.close()


# @ac AC-FRONT-029.5
async def test_ac_front_029_5_space_after_the_name_hides_the_list():
    session, app = await chat_frontend([answering("sol")])
    async with app.run_test() as pilot:
        await pilot.press("@", "s", "o", "l")
        assert visible(app)
        await pilot.press("space")
        assert not visible(app)
    await session.close()


# @ac AC-FRONT-029.6
async def test_ac_front_029_6_no_answering_peers_means_no_list():
    session, app = await chat_frontend([listening("arquivo")])
    async with app.run_test() as pilot:
        await pilot.press("@")
        assert not visible(app)
        assert not app.has_suggestions()
    await session.close()


# @ac AC-FRONT-029.7
async def test_ac_front_029_7_an_at_sign_later_in_the_line_opens_nothing():
    session, app = await chat_frontend([answering("sol")])
    async with app.run_test() as pilot:
        await pilot.press("a", "s", "k", "space", "@")
        assert not visible(app)
        await pilot.press("s")
        assert not visible(app)
    await session.close()


# @ac AC-FRONT-029.8
async def test_ac_front_029_8_tab_completes_the_highlighted_peer():
    session, app = await chat_frontend([answering("sol"), answering("lua")])
    async with app.run_test() as pilot:
        inp = app.query_one("#input-line", CommandInput)
        await pilot.press("@", "s")
        await pilot.press("tab")
        assert inp.text == "@sol "
        assert not visible(app)
        assert app.messages == []
    await session.close()


# @ac AC-FRONT-029.9
async def test_ac_front_029_9_down_then_up_moves_the_highlight():
    session, app = await chat_frontend([answering("sol"), answering("lua")])
    async with app.run_test() as pilot:
        inp = app.query_one("#input-line", CommandInput)
        # Sorted by name: "lua" first, "sol" second.
        await pilot.press("@", "down", "tab")
        assert inp.text == "@sol "
        inp.clear()
        await pilot.press("@", "down", "up", "tab")
        assert inp.text == "@lua "
    await session.close()


# @ac AC-FRONT-029.10
async def test_ac_front_029_10_enter_accepts_the_peer_instead_of_submitting():
    session, app = await chat_frontend([answering("sol")])
    async with app.run_test() as pilot:
        inp = app.query_one("#input-line", CommandInput)
        await pilot.press("@", "s")
        await pilot.press("enter")
        assert inp.text == "@sol "
        await pilot.pause()
        assert app.messages == []
    await session.close()


# @ac AC-FRONT-029.11
async def test_ac_front_029_11_escape_hides_the_list_without_changing_the_input():
    session, app = await chat_frontend([answering("sol")])
    async with app.run_test() as pilot:
        inp = app.query_one("#input-line", CommandInput)
        await pilot.press("@", "s")
        await pilot.press("escape")
        assert not visible(app)
        assert inp.text == "@s"
    await session.close()


# @ac AC-FRONT-029.12
async def test_ac_front_029_12_a_completed_peer_is_asked():
    sol, lua = answering("sol"), answering("lua")
    session, app = await chat_frontend([sol, lua])
    async with app.run_test() as pilot:
        await pilot.press("@", "s", "tab")
        await pilot.press(*"chove")
        await pilot.press("enter")
        await pilot.pause()
    await session.close()
    assert sol.asked == ["chove"]
    assert lua.asked == []


# @ac AC-FRONT-029.13
async def test_ac_front_029_13_a_peer_registered_later_is_listed():
    session, app = await chat_frontend([answering("sol")])
    async with app.run_test() as pilot:
        session.add_connector(answering("lua"))
        await pilot.press("@")
        assert offered(app) == {"@sol", "@lua"}
    await session.close()


# @ac AC-FRONT-029.14
async def test_ac_front_029_14_two_peers_sharing_a_name_are_listed_once():
    session, app = await chat_frontend([answering("sol"), answering("sol")])
    async with app.run_test() as pilot:
        await pilot.press("@")
        assert visible(app)
        options = [o.id for o in app.query_one("#suggestions", OptionList).options]
        assert options == ["@sol"]
        assert app.is_running
    await session.close()
