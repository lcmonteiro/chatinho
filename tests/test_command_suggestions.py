"""Tests for the command-suggestion (autocomplete) popup.

Commands are registered via ``create_chat(commands={...})``; the popup shows
matches for the "/token" currently being typed, and Tab/Down/Up/Escape
drive it without stealing focus from the input.
"""

import pytest
from textual.widgets import Input, OptionList

from chatinho import BaseCommand, create_chat


class _StubCommand(BaseCommand):
    """Command that only exists to be listed by the suggestion popup."""

    def execute(self, *args, **kwargs) -> None:
        return None


COMMANDS = {
    "help"    : _StubCommand("help", "Show help"),
    "history" : _StubCommand("history", "Show history"),
    "hello"   : _StubCommand("hello", ""),
}


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
    app = create_chat(commands=COMMANDS)
    async with app.run_test() as pilot:
        suggestions = app.query_one("#command-suggestions", OptionList)
        await pilot.press("/")
        assert suggestions.has_class("-visible")
        assert {o.id for o in suggestions.options} == set(COMMANDS)


@pytest.mark.asyncio
async def test_typing_filters_suggestions_by_prefix():
    app = create_chat(commands=COMMANDS)
    async with app.run_test() as pilot:
        suggestions = app.query_one("#command-suggestions", OptionList)
        await pilot.press("/", "h", "e")
        assert {o.id for o in suggestions.options} == {"help", "hello"}


@pytest.mark.asyncio
async def test_no_match_hides_suggestions():
    app = create_chat(commands=COMMANDS)
    async with app.run_test() as pilot:
        suggestions = app.query_one("#command-suggestions", OptionList)
        await pilot.press("/", "z")
        assert not suggestions.has_class("-visible")
        assert suggestions.option_count == 0


@pytest.mark.asyncio
async def test_space_after_token_hides_suggestions():
    """Once a full command is followed by a space, it's no longer being typed."""
    app = create_chat(commands=COMMANDS)
    async with app.run_test() as pilot:
        suggestions = app.query_one("#command-suggestions", OptionList)
        await pilot.press("/", "h", "e", "l", "p", "space")
        assert not suggestions.has_class("-visible")


@pytest.mark.asyncio
async def test_tab_completes_highlighted_suggestion():
    app = create_chat(commands=COMMANDS)
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
    app = create_chat(commands=COMMANDS)
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
    app = create_chat(commands=COMMANDS)
    async with app.run_test() as pilot:
        inp = app.query_one("#input-line", Input)
        await pilot.press("/", "h", "e")
        await pilot.press("enter")
        assert inp.value == "/hello "
        assert len(app.messages) == 0  # not submitted yet


@pytest.mark.asyncio
async def test_escape_hides_suggestions_without_changing_input():
    app = create_chat(commands=COMMANDS)
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
    app = create_chat(commands=COMMANDS)
    async with app.run_test() as pilot:
        focused_before = app.focused
        await pilot.press("x")  # not a command prefix — no popup
        await pilot.press("tab")
        assert app.focused is not focused_before


@pytest.mark.asyncio
async def test_unregistered_command_still_dispatches():
    """Autocomplete is advisory only — unlisted commands still work."""
    commands_seen = []
    app = create_chat(command_handler=commands_seen.append, commands=COMMANDS)
    async with app.run_test():
        app.send_command("stats")
    assert commands_seen == ["stats"]
