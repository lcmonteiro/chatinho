"""Tests for the command-suggestion (autocomplete) popup.

A command is an ask to a tool, so the popup lists the participants that
can be asked. They are registered via ``create_chat(participants=[...])``; the popup shows
matches for the "/token" currently being typed, and Tab/Down/Up/Escape
drive it without stealing focus from the input.
"""

import pytest
from textual.widgets import Input, OptionList

from chatinho import HookOnAsk, create_chat, require, tool


def stub(name: str, description: str):
    """Builds a tool that only exists to be listed by the popup."""
    @tool(name, description)
    @require(HookOnAsk)
    class _Stub:
        async def on_ask(self, msg) -> None:
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
    app = create_chat()
    async with app.run_test() as pilot:
        suggestions = app.query_one("#command-suggestions", OptionList)
        await pilot.press("/")
        assert not suggestions.has_class("-visible")
        assert not app.has_command_suggestions()


@pytest.mark.asyncio
async def test_slash_alone_lists_all_commands():
    app = create_chat(participants=COMMANDS)
    async with app.run_test() as pilot:
        suggestions = app.query_one("#command-suggestions", OptionList)
        await pilot.press("/")
        assert suggestions.has_class("-visible")
        assert {o.id for o in suggestions.options} == COMMAND_NAMES


@pytest.mark.asyncio
async def test_typing_filters_suggestions_by_prefix():
    app = create_chat(participants=COMMANDS)
    async with app.run_test() as pilot:
        suggestions = app.query_one("#command-suggestions", OptionList)
        await pilot.press("/", "h", "e")
        assert {o.id for o in suggestions.options} == {"help", "hello"}


@pytest.mark.asyncio
async def test_no_match_hides_suggestions():
    app = create_chat(participants=COMMANDS)
    async with app.run_test() as pilot:
        suggestions = app.query_one("#command-suggestions", OptionList)
        await pilot.press("/", "z")
        assert not suggestions.has_class("-visible")
        assert suggestions.option_count == 0


@pytest.mark.asyncio
async def test_space_after_token_hides_suggestions():
    """Once a full command is followed by a space, it's no longer being typed."""
    app = create_chat(participants=COMMANDS)
    async with app.run_test() as pilot:
        suggestions = app.query_one("#command-suggestions", OptionList)
        await pilot.press("/", "h", "e", "l", "p", "space")
        assert not suggestions.has_class("-visible")


@pytest.mark.asyncio
async def test_tab_completes_highlighted_suggestion():
    app = create_chat(participants=COMMANDS)
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
    app = create_chat(participants=COMMANDS)
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
    app = create_chat(participants=COMMANDS)
    async with app.run_test() as pilot:
        inp = app.query_one("#input-line", Input)
        await pilot.press("/", "h", "e")
        await pilot.press("enter")
        assert inp.value == "/hello "
        assert len(app.messages) == 0  # not submitted yet


@pytest.mark.asyncio
async def test_escape_hides_suggestions_without_changing_input():
    app = create_chat(participants=COMMANDS)
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
    app = create_chat(participants=COMMANDS)
    async with app.run_test() as pilot:
        focused_before = app.focused
        await pilot.press("x")  # not a command prefix — no popup
        await pilot.press("tab")
        assert app.focused is not focused_before


@pytest.mark.asyncio
async def test_an_unknown_command_says_so_instead_of_vanishing():
    """There is no dispatch to fall through: an unknown name has no id."""
    app = create_chat(participants=COMMANDS)
    async with app.run_test() as pilot:
        inp = app.query_one("#input-line", Input)
        inp.value = "/nao-existe"
        await pilot.press("enter")
        await pilot.pause()
    assert app.messages[-1].text == "Unknown command: /nao-existe"
