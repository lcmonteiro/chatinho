"""The command input line and its autocomplete popup.

:class:`CommandSuggestions` owns the popup's options and visibility;
:class:`CommandInput` drives it through the sibling widget rather than
reaching up into the application.
"""

import logging
from typing import Any, List, Optional, Tuple

from textual.app import ScreenStackError
from textual.binding import Binding
from textual.css.query import NoMatches
from textual.widgets import Input, OptionList
from textual.widgets.option_list import Option



logger = logging.getLogger(__name__)

COMMAND_PREFIX : str = "/"

SUGGESTIONS_ID : str = "command-suggestions"


class CommandSuggestions(OptionList):
    """Popup listing the commands whose name matches the "/token" being typed."""

    def __init__(self, commands: Any, **kwargs) -> None:
        super().__init__(**kwargs)
        # Held by reference: the application owns the dict and keeps it current.
        self._commands = commands

    @property
    def has_suggestions(self) -> bool:
        """Whether the popup currently has entries."""
        return self.option_count > 0

    def update_for(self, text: str) -> None:
        """Shows the commands matching *text*, or hides the popup if none do.

        Args:
            text: The current content of the input line.
        """
        matches = []
        if text.startswith(COMMAND_PREFIX) and " " not in text:
            token = text[len(COMMAND_PREFIX):]
            matches = sorted(n for n in self._names() if n.startswith(token))

        if not matches:
            self.hide()
            return

        self.set_options(Option(self._label(name), id=name) for name in matches)
        self.highlighted = 0
        self.add_class("-visible")

    def hide(self) -> None:
        """Hides and clears the popup."""
        self.remove_class("-visible")
        self.clear_options()

    def move(self, delta: int) -> None:
        """Moves the highlight up (delta<0) or down (delta>0)."""
        if delta > 0:
            self.action_cursor_down()
        else:
            self.action_cursor_up()

    def take_highlighted(self) -> Optional[str]:
        """Returns the highlighted command name and hides the popup.

        Returns:
            Optional[str]: The command name, or None if nothing is highlighted.
        """
        option = self.highlighted_option
        if option is None or option.id is None:
            return None
        name = option.id
        self.hide()
        return name

    def _names(self) -> List[str]:
        """The names of the registered commands."""
        return list(self._commands)

    def _tool(self, name: str) -> Any:
        """The command with that name, or None."""
        return self._commands.get(name)

    def _label(self, name: str) -> str:
        """Returns the popup label for the command registered as *name*."""
        description = getattr(self._tool(name), "description", "")
        if description:
            return f"{COMMAND_PREFIX}{name}  —  {description}"
        return f"{COMMAND_PREFIX}{name}"


class CommandInput(Input):
    """Input that drives the sibling :class:`CommandSuggestions` popup.

    Tab/Down/Up/Escape are only claimed while a suggestion popup is open
    (see ``check_action``) — otherwise they fall through to Textual's
    normal bindings (e.g. Tab still moves focus as usual).
    """

    BINDINGS = [
        Binding("tab", "accept_suggestion", show=False),
        Binding("down", "next_suggestion", show=False),
        Binding("up", "prev_suggestion", show=False),
        Binding("escape", "dismiss_suggestions", show=False),
    ]

    @property
    def suggestions(self) -> Optional[CommandSuggestions]:
        """The sibling popup, or None before the widget tree exists."""
        try:
            return self.screen.query_one(f"#{SUGGESTIONS_ID}", CommandSuggestions)
        except (NoMatches, ScreenStackError):
            # Bindings are checked before the widget tree exists too.
            return None

    def accept_suggestion(self) -> bool:
        """Completes the input with the highlighted suggestion, if any.

        Returns:
            bool: True if a suggestion was accepted.
        """
        suggestions = self.suggestions
        if suggestions is None:
            return False
        name = suggestions.take_highlighted()
        if name is None:
            return False
        self.value = f"{COMMAND_PREFIX}{name} "
        self.action_end()
        return True

    def check_action(self, action: str, parameters: Tuple[object, ...]) -> Optional[bool]:
        if action in ("accept_suggestion", "next_suggestion", "prev_suggestion", "dismiss_suggestions"):
            suggestions = self.suggestions
            return suggestions is not None and suggestions.has_suggestions
        return True

    def action_accept_suggestion(self) -> None:
        self.accept_suggestion()

    def action_next_suggestion(self) -> None:
        if self.suggestions is not None:
            self.suggestions.move(1)

    def action_prev_suggestion(self) -> None:
        if self.suggestions is not None:
            self.suggestions.move(-1)

    def action_dismiss_suggestions(self) -> None:
        if self.suggestions is not None:
            self.suggestions.hide()

    async def action_submit(self) -> None:
        suggestions = self.suggestions
        if suggestions is not None and suggestions.has_suggestions and self.accept_suggestion():
            return
        await super().action_submit()
