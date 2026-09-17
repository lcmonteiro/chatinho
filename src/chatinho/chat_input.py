"""The command input line and its autocomplete popup.

:class:`CommandSuggestions` owns the popup's options and visibility;
:class:`CommandInput` drives it through the sibling widget rather than
reaching up into the application.

The input is a :class:`~textual.widgets.TextArea` rather than an ``Input``
because a message may span lines: **Enter sends, Shift+Enter (or Alt+Enter)
opens a new line.** ``Input`` is single-line by construction, so there was
nowhere to put the second line.
"""

import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

from textual import events
from textual.app import ScreenStackError
from textual.binding import Binding
from textual.css.query import NoMatches
from textual.message import Message
from textual.widgets import OptionList, TextArea
from textual.widgets.option_list import Option



logger = logging.getLogger(__name__)

COMMAND_PREFIX : str = "/"

SUGGESTIONS_ID : str = "command-suggestions"

#: The keys that open a new line instead of sending. ``ctrl+j`` is the only
#: one that needs no enhanced keyboard protocol to arrive — it is Line Feed,
#: a byte of its own, where the rest are a modified Return — so it must stay:
#: a test fails if every key in here depends on a protocol, and names what
#: each of the others degrades to without one. The way in that needs no key at
#: all is :data:`NEWLINE_ESCAPE` before Enter, in
#: :meth:`CommandInput._open_line_at_the_escape`.
NEWLINE_KEYS : Tuple[str, ...] = ("ctrl+enter", "ctrl+j", "shift+enter", "alt+enter")

#: The character that, typed just before Enter, opens a line instead of
#: sending — and is consumed doing it. A **space**: ending a line with one and
#: carrying on is what continuing already feels like, so the gesture is the
#: intention rather than a code for it. Set it to another character, or to
#: None to turn it off, with ``build_chat(newline_escape=…)``.
NEWLINE_ESCAPE : str = " "


def validate_escape(char: Optional[str]) -> Optional[str]:
    """Checks the escape character, or None for no escape at all.

    Args:
        char: One character, or None to disable the escape.

    Returns:
        Optional[str]: *char*, unchanged.

    Raises:
        ValueError: If it is not a single character, or is a newline — which
            could never match, since the escape is looked for on the cursor's
            own line and a line never holds one. That is precisely the silent
            nothing the key validator next door exists to prevent.
    """
    if char is None:
        return None
    if not isinstance(char, str) or len(char) != 1:
        raise ValueError(
            "newline_escape must be a single character or None, got %r" % (char,))
    if char == "\n":
        raise ValueError(
            "newline_escape cannot be a newline: it is looked for on the cursor's "
            "own line, which never holds one, so it would simply never fire")
    return char


class CommandSuggestions(OptionList):
    """Popup listing the commands whose name matches the "/token" being typed."""

    def __init__(self, commands: Callable[[], Dict[str, Any]], **kwargs) -> None:
        super().__init__(**kwargs)
        # Granted by HookCommands: called fresh each time, never held as a dict.
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
        return list(self._commands())

    def _tool(self, name: str) -> Any:
        """The command with that name, or None."""
        return self._commands().get(name)

    def _label(self, name: str) -> str:
        """Returns the popup label for the command registered as *name*."""
        description = getattr(self._tool(name), "description", "")
        if description:
            return f"{COMMAND_PREFIX}{name}  —  {description}"
        return f"{COMMAND_PREFIX}{name}"


class CommandInput(TextArea):
    """Multi-line input that drives the sibling :class:`CommandSuggestions` popup.

    Enter sends what was typed as :class:`CommandInput.Submitted`; the keys in
    :data:`NEWLINE_KEYS`, and :attr:`newline_escape` typed just before it, open
    a new line instead. Tab and Escape are only claimed while the popup is open (see
    ``check_action``), so Tab still moves
    focus as usual. Up and Down move the suggestion highlight when the popup is
    open and the cursor between lines when it is not — a multi-line input needs
    them for both.
    """

    class Submitted(Message):
        """Posted when Enter sends the line.

        Attributes:
            input: The input that sent it.
            text: What was typed, stripped. Never empty — Enter on a blank
                input sends nothing at all.
        """

        def __init__(self, input: "CommandInput", text: str) -> None:
            super().__init__()
            self.input = input
            self.text = text

        @property
        def control(self) -> "CommandInput":
            """The input that sent it, under the name Textual expects."""
            return self.input

    BINDINGS = [
        Binding("tab", "accept_suggestion", show=False),
        Binding("down", "next_suggestion", show=False),
        Binding("up", "prev_suggestion", show=False),
        Binding("escape", "dismiss_suggestions", show=False),
    ]

    def __init__(self, newline_escape: Optional[str] = NEWLINE_ESCAPE, **kwargs) -> None:
        #: Typed just before Enter, opens a line instead of sending. None: none.
        self.newline_escape : Optional[str] = validate_escape(newline_escape)
        # No cursor-line highlight: the input is drawn as an outline, and a
        # filled row would be the one background in it.
        kwargs.setdefault("soft_wrap", True)
        kwargs.setdefault("highlight_cursor_line", False)
        super().__init__(**kwargs)

    @property
    def suggestions(self) -> Optional[CommandSuggestions]:
        """The sibling popup, or None before the widget tree exists."""
        try:
            return self.screen.query_one(f"#{SUGGESTIONS_ID}", CommandSuggestions)
        except (NoMatches, ScreenStackError):
            # Bindings are checked before the widget tree exists too.
            return None

    @property
    def _popup_is_open(self) -> bool:
        """Whether there is a suggestion to move through or accept."""
        suggestions = self.suggestions
        return suggestions is not None and suggestions.has_suggestions

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
        self.text = f"{COMMAND_PREFIX}{name} "
        self.move_cursor(self.document.end)
        return True

    def submit(self) -> bool:
        """Sends what was typed, or accepts a suggestion if the popup is open.

        Returns:
            bool: True if a suggestion was accepted instead of sending.
        """
        if self._popup_is_open and self.accept_suggestion():
            return True
        text = self.text.strip()
        if text:
            self.post_message(self.Submitted(self, text))
        return False

    def _open_line_at_the_escape(self) -> bool:
        """Turns :attr:`newline_escape` immediately before the cursor into a line.

        The second way in, and the only one needing no key a terminal might not
        report: the escape is a *character*, and Enter is the key everyone has.
        Claude Code ships this too, as a backslash; the default here is a space,
        because ending a line with one and carrying on is what continuing
        already feels like — the gesture is the intention rather than a code
        for it.

        It is anchored to the **cursor**, not to the end of the text, and that
        is what leaves a way to send a message which really does end in the
        escape: move off the end, and Enter sends. There is no other escape —
        doubling the character is not one. With a space that costs little,
        since :meth:`submit` strips what it sends anyway.

        ``None`` needs no branch of its own and deliberately has none: no
        character equals it, so the comparison below already never fires. An
        early return for it was here and was deleted, because nothing could be
        broken to make a test notice it.

        Returns:
            bool: True when a line was opened. False when the escape was not
            there, or is off, and Enter means what it usually means.
        """
        row, column = self.cursor_location
        if column == 0 or self.document.get_line(row)[column - 1] != self.newline_escape:
            return False
        self.replace("\n", (row, column - 1), (row, column))
        return True

    async def _on_key(self, event: events.Key) -> None:
        """Claims Enter for sending, and the newline keys for a second line.

        Enter only sends when the escape character does not precede the cursor;
        that is the second way to open a line, and the only one no terminal can
        swallow.

        ``TextArea`` inserts on Enter from inside its own key handler rather
        than through a binding, so a ``Binding("enter", …)`` here would never
        be reached. This is the only place the two can be told apart.
        """
        if event.key in NEWLINE_KEYS:
            event.stop()
            event.prevent_default()
            self.insert("\n")
            return
        if event.key == "enter":
            event.stop()
            event.prevent_default()
            if not self._open_line_at_the_escape():
                self.submit()
            return
        await super()._on_key(event)

    def check_action(self, action: str, parameters: Tuple[object, ...]) -> Optional[bool]:
        # Up and Down are always ours: they fall back to moving the cursor.
        if action in ("accept_suggestion", "dismiss_suggestions"):
            return self._popup_is_open
        return True

    def action_accept_suggestion(self) -> None:
        self.accept_suggestion()

    def action_next_suggestion(self) -> None:
        if self._popup_is_open and self.suggestions is not None:
            self.suggestions.move(1)
        else:
            self.action_cursor_down()

    def action_prev_suggestion(self) -> None:
        if self._popup_is_open and self.suggestions is not None:
            self.suggestions.move(-1)
        else:
            self.action_cursor_up()

    def action_dismiss_suggestions(self) -> None:
        if self.suggestions is not None:
            self.suggestions.hide()
