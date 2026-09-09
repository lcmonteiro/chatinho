"""Tests for the command-suggestion (autocomplete) popup.

The popup lists the registered commands. They are registered via ``chat_app(commands=[...])``; the popup shows
matches for the "/token" currently being typed, and Tab/Down/Up/Escape
drive it without stealing focus from the input.
"""

import pytest
from textual.widgets import Input, OptionList

from chatinho import ChatSession, HookExecute, require, tool
from chatinho.chat_app import _Chat


def chat_app(connectors=None, commands=None, backend=None, **kwargs):
    """The terminal peer, built and attached the way create_chat does it.

    ``create_chat`` returns the *session* now — the terminal is one of its
    peers, not its owner — so a test that drives the app builds it the same way
    a caller would: an ordinary connector, attached to an ordinary session.
    """
    session = ChatSession(connectors=connectors, commands=commands, backend=backend)
    return _Chat(session=session, **kwargs)


def stub(name: str, description: str):
    """Builds a tool that only exists to be listed by the popup."""
    @tool(name, description)
    @require(HookExecute)
    class _Stub:
        async def execute(self, args="", **kwargs) -> None:
            return None
    return _Stub()


COMMANDS = [
    stub("help", "Show help"),
    stub("history", "Show history"),
    stub("hello", ""),
]
COMMAND_NAMES = {"help", "history", "hello"}


@pytest.mark.asyncio
async def test_no_suggestions_without_registered_commands():
    app = chat_app()
    async with app.run_test() as pilot:
        suggestions = app.query_one("#command-suggestions", OptionList)
        await pilot.press("/")
        assert not suggestions.has_class("-visible")
        assert not app.has_command_suggestions()


@pytest.mark.asyncio
async def test_slash_alone_lists_all_commands():
    app = chat_app(commands=COMMANDS)
    async with app.run_test() as pilot:
        suggestions = app.query_one("#command-suggestions", OptionList)
        await pilot.press("/")
        assert suggestions.has_class("-visible")
        assert {o.id for o in suggestions.options} == COMMAND_NAMES


@pytest.mark.asyncio
async def test_typing_filters_suggestions_by_prefix():
    app = chat_app(commands=COMMANDS)
    async with app.run_test() as pilot:
        suggestions = app.query_one("#command-suggestions", OptionList)
        await pilot.press("/", "h", "e")
        assert {o.id for o in suggestions.options} == {"help", "hello"}


@pytest.mark.asyncio
async def test_no_match_hides_suggestions():
    app = chat_app(commands=COMMANDS)
    async with app.run_test() as pilot:
        suggestions = app.query_one("#command-suggestions", OptionList)
        await pilot.press("/", "z")
        assert not suggestions.has_class("-visible")
        assert suggestions.option_count == 0


@pytest.mark.asyncio
async def test_space_after_token_hides_suggestions():
    """Once a full command is followed by a space, it's no longer being typed."""
    app = chat_app(commands=COMMANDS)
    async with app.run_test() as pilot:
        suggestions = app.query_one("#command-suggestions", OptionList)
        await pilot.press("/", "h", "e", "l", "p", "space")
        assert not suggestions.has_class("-visible")


@pytest.mark.asyncio
async def test_tab_completes_highlighted_suggestion():
    app = chat_app(commands=COMMANDS)
    async with app.run_test() as pilot:
        inp = app.query_one("#input-line", Input)
        suggestions = app.query_one("#command-suggestions", OptionList)
        await pilot.press("/", "h", "e")
        # "hello" sorts before "help" — first match is highlighted by default.
        await pilot.press("tab")
        assert inp.value == "/hello "
        assert not suggestions.has_class("-visible")


@pytest.mark.asyncio
async def test_down_moves_highlight_then_tab_completes_it():
    app = chat_app(commands=COMMANDS)
    async with app.run_test() as pilot:
        inp = app.query_one("#input-line", Input)
        suggestions = app.query_one("#command-suggestions", OptionList)
        await pilot.press("/", "h", "e")
        first = suggestions.highlighted_option.id
        await pilot.press("down")
        second = suggestions.highlighted_option.id
        assert second != first
        await pilot.press("tab")
        assert inp.value == f"/{second} "


@pytest.mark.asyncio
async def test_enter_accepts_suggestion_instead_of_submitting():
    app = chat_app(commands=COMMANDS)
    async with app.run_test() as pilot:
        inp = app.query_one("#input-line", Input)
        await pilot.press("/", "h", "e")
        await pilot.press("enter")
        assert inp.value == "/hello "
        assert len(app.messages) == 0  # not submitted yet


@pytest.mark.asyncio
async def test_escape_hides_suggestions_without_changing_input():
    app = chat_app(commands=COMMANDS)
    async with app.run_test() as pilot:
        inp = app.query_one("#input-line", Input)
        suggestions = app.query_one("#command-suggestions", OptionList)
        await pilot.press("/", "h")
        await pilot.press("escape")
        assert not suggestions.has_class("-visible")
        assert inp.value == "/h"


@pytest.mark.asyncio
async def test_tab_falls_through_to_focus_next_without_suggestions():
    """Tab must keep its normal Textual behavior when no popup is open."""
    app = chat_app(commands=COMMANDS)
    async with app.run_test() as pilot:
        focused_before = app.focused
        await pilot.press("x")  # not a command prefix — no popup
        await pilot.press("tab")
        assert app.focused is not focused_before


@pytest.mark.asyncio
async def test_an_unknown_command_says_so_instead_of_vanishing():
    """There is no dispatch to fall through: an unknown name has no id."""
    app = chat_app(commands=COMMANDS)
    async with app.run_test() as pilot:
        inp = app.query_one("#input-line", Input)
        inp.value = "/nao-existe"
        await pilot.press("enter")
        await pilot.pause()
    assert app.messages[-1].text == "Unknown command: /nao-existe"
