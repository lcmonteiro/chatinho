"""The scrollable chat log and the message bubbles it mounts.

:class:`ChatLog` owns its own children: which messages are currently rendered,
their widgets, and which one is selected as the reply target. The application
only tells it when the history changed.
"""

import asyncio
import logging
import time
from typing import Callable, Dict, List, Optional

from textual import events
from textual.containers import ScrollableContainer, Vertical
from textual.widget import Widget
from textual.widgets import Markdown, Static

from . import chat_clipboard
from .chat_hooks import name_of
from .chat_message import TOOL, ChatMessage
from .chat_style import ChatStyle

logger = logging.getLogger(__name__)

#: What a bubble costs around its text: `padding: 1 2` either side, plus the
#: two cells its `border: round` draws in. The stylesheet zeroes `Markdown`'s
#: own `padding: 0 2 0 2` so it is not four more that this does not count —
#: a line measured to fit would otherwise wrap.
_BUBBLE_CHROME : int = 6

#: How long after a tap a second one still counts as a double.
#: Textual's own `CLICK_CHAIN_TIME_THRESHOLD` is half a second; this is a
#: little longer, because two taps with a thumb are further apart than two
#: with a mouse.
_A_DOUBLE : float = 0.7

#: How far the second tap may land from the first and still be a double.
#: Textual's `Click.chain` demands the *exact same cell*, which a finger will
#: not reproduce — that is why the chain count is not used here.
_A_WOBBLE : int = 1

#: How far a press may wander between landing and lifting and still be a tap
#: rather than the log being panned. It is measured on both axes, and it is
#: the *second* of the two things that say a press was not a tap — a selection
#: the screen is still holding is the first, and the only one that catches a
#: drag shorter than this.
_A_DRAG : int = 2

#: How long the copy confirmation stays up. Long enough to read on a phone,
#: which is where a copy is hardest to be sure of.
_CONFIRMATION : float = 5.0

#: What a bubble adds to its header's width to sit under it: the header's own
#: `margin-left`, plus one space so the two do not end flush.
_HEADER_SLACK : int = 2


def preview_of(text: str, width: int = 60) -> str:
    """A single line of *text*, short enough to sit in a popup.

    The confirmation shows what was copied rather than only that something
    was: on a phone, where the clipboard cannot be checked without leaving
    the chat, seeing the words back is the confirmation.

    Args:
        text: What was copied.
        width: How much of it to show before trailing off.

    Returns:
        str: The text collapsed onto one line, cut to *width*.
    """
    flat = " ".join(text.split())
    return flat if len(flat) <= width else flat[:width - 1] + "…"


class TouchScrollableContainer(ScrollableContainer):
    """Scrollable container that pans by dragging, where there is nothing to select.

    **A terminal cannot tell a finger from a mouse.** Termux turns a swipe into
    the same SGR mouse report a trackpad sends, and no mouse protocol any
    terminal speaks carries the device — Textual's `MouseEvent` has no field
    for it because there is nothing to put there. So the gesture is split by
    *what it landed on* rather than by what made it: from Textual 3 a drag is
    already a text selection, so a drag that starts on text belongs to Textual,
    and only one that starts where there is nothing to select pans the log.

    Both used to run at once, and that is what shook: the selection extended to
    the pointer while the pan moved the text out from under it.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._panning        : bool = False
        self._drag_start_y   : int  = 0
        self._scroll_start_y : int  = 0

    def on_mouse_down(self, event: events.MouseDown) -> None:
        """Starts a pan, if the press landed where there is no text to select.

        The screen reports no content offset for a coordinate holding nothing
        selectable — the log's background, the margin beside a bubble — and
        that is the whole of the test. Textual anchored a selection on this
        same press before the event reached here, so a pan drops it: clearing
        `_select_state` is also what stops Textual's own select-auto-scroll
        from reaching for the same offset this is about to drive.
        """
        _, offset = self.screen.get_widget_and_offset_at(int(event.screen_x), int(event.screen_y))
        self._panning = offset is None
        if not self._panning:
            return                      # the drag is Textual's, to select with
        self.screen.clear_selection()
        # `screen_y`, never `event.y`: a bubbled mouse event carries
        # coordinates relative to whatever descendant it first landed on, and
        # the pan puts a *different* descendant under the pointer by the next
        # report. Mixing the two frames is what made the scroll stutter — five
        # cells of travel moved the log two, in a 0/1/0/1 limp.
        self._drag_start_y   = int(event.screen_y)
        self._scroll_start_y = int(self.scroll_offset.y)
        event.stop()

    def on_mouse_move(self, event: events.MouseMove) -> None:
        """Pans the log, while a pan is what this drag is."""
        if not self._panning or not event.button:
            return
        delta_y  = int(event.screen_y) - self._drag_start_y
        target_y = self._scroll_start_y - delta_y
        max_y    = self.max_scroll_y
        if max_y > 0:
            target_y = max(0, min(target_y, max_y))
            self.scroll_to(y=target_y, animate=False)
        event.stop()

    def on_mouse_up(self, event: events.MouseUp) -> None:
        """Ends the pan, if there was one."""
        if not self._panning:
            return
        self._panning = False
        event.stop()


class _MessageContainer(Vertical):
    """One message: its header, the bubble under it, and what a tap means.

    One tap selects the message as the reply target; **two copy its text**.
    """

    def __init__(
        self,
        *children: Widget,
        msg_id: str,
        on_select: Callable[[str], None],
        on_copy: Callable[[str], None],
        **kwargs,
    ) -> None:
        super().__init__(*children, **kwargs)
        self.msg_id = msg_id
        self._on_select = on_select
        self._on_copy = on_copy
        self._pressed_x   : Optional[int] = None
        self._pressed_y   : Optional[int] = None
        self._last_tap_at : float = 0.0
        self._last_tap_y  : int = 0

    def on_mouse_down(self, event: events.MouseDown) -> None:
        """Remembers where the press landed, to tell a tap from a drag.

        Deliberately does not stop the event: a drag across a message is
        Textual's to read as a text selection, and the log reads the same
        events to pan, so a message that swallowed them would be a message
        you could neither select from nor scroll past.
        """
        self._pressed_x = event.screen_x
        self._pressed_y = event.screen_y

    def on_click(self, event: events.Click) -> None:
        """Selects on one tap and copies on two, ignoring a scroll.

        ``event.chain`` is deliberately not used. Textual counts a double
        click only when both land on the *exact same cell*, which is right for
        a mouse and wrong for a thumb; this allows the second tap a cell of
        wobble, and a little longer to arrive.

        Two things say this was not a tap, and they cover different gestures.
        **A selection is what the screen is holding**: Textual clears it when
        the press and the release share a cell, so text left selected means
        the pointer dragged across it — true even of the one- and two-cell
        drags a travel threshold has to let through as wobble. And a press
        that *travelled* was the log being panned, which selects nothing and
        so leaves the first signal silent.
        """
        pressed_x, self._pressed_x = self._pressed_x, None
        pressed_y, self._pressed_y = self._pressed_y, None
        if self.screen.get_selected_text() is not None:
            return                      # text was selected, not a message tapped
        travelled = (
            (pressed_x is not None and abs(event.screen_x - pressed_x) > _A_DRAG)
            or (pressed_y is not None and abs(event.screen_y - pressed_y) > _A_DRAG)
        )
        if travelled:
            return                      # the log was panned, not tapped

        now = time.monotonic()
        doubled = (now - self._last_tap_at <= _A_DOUBLE
                   and abs(event.screen_y - self._last_tap_y) <= _A_WOBBLE)
        self._last_tap_at, self._last_tap_y = now, event.screen_y

        # Selecting is a toggle, and the first tap of the pair already did it.
        # Doing it again puts the reply target back where it was, so a double
        # tap only copies — which is what the long press it replaces did.
        self._on_select(self.msg_id)
        if doubled:
            self._last_tap_at = 0.0     # a third tap starts a new pair
            self._on_copy(self.msg_id)
        event.stop()


class ChatLog(TouchScrollableContainer):
    """Renders the last ``max_displayed`` messages the chat will hand over.

    Reads through ``context`` — the capability the presentation was
    granted — rather than holding the history itself. Messages leaving the
    window are unmounted from the terminal, not forgotten.
    """

    def __init__(
        self,
        context : Callable[..., List[ChatMessage]],
        peers : Optional[Callable[[], Dict[int, object]]] = None,
        max_displayed : int = 100,
        style : Optional[ChatStyle] = None,
        on_reply_target_change : Optional[Callable[[Optional[str]], None]] = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        # The same style the stylesheet was rendered from: the header colours
        # are CSS, but the widest a bubble may grow is applied here, because
        # only this knows how wide the text actually is.
        self.style : ChatStyle = style or ChatStyle()
        # Not `_context`: Textual's MessagePump owns that name as a context
        # manager, and shadowing it hangs the widget's message loop.
        self._read_context = context
        # Granted by HookPeers: called fresh each time, never held as a dict —
        # a peer may be registered after this widget was built.
        self._read_peers = peers
        self.max_displayed : int = max_displayed
        self._on_reply_target_change = on_reply_target_change
        self._msg_widgets : Dict[str, Widget] = {}
        # IDs of the messages currently rendered, in order
        self._rendered_msg_ids : List[str] = []
        # Message selected as reply target (via click)
        self.reply_target : Optional[str] = None

    # === Rendering ==================================================================

    def sync(self) -> None:
        """Brings the rendered widgets in line with the store's window.

        Mounts messages that entered the window and unmounts those that left,
        keeping the number of widgets in the terminal bounded.
        """
        # Only auto-scrolls if the user is already at the bottom (otherwise they
        # lose their reading position)
        was_at_bottom = self.scroll_offset.y >= (self.max_scroll_y - 1)

        desired_ids = [m.id for m in self._read_context(limit=self.max_displayed)]
        current = set(self._rendered_msg_ids)
        desired = set(desired_ids)

        # Unmount messages that left the window
        for msg_id in self._rendered_msg_ids:
            if msg_id not in desired:
                widget = self._msg_widgets.pop(msg_id, None)
                if widget is not None:
                    widget.remove()

        # Mount the new ones, in the correct order
        for msg_id in desired_ids:
            if msg_id not in current:
                msg = self._find(msg_id)
                if msg is not None:
                    self.mount(self._render_message(msg))

        self._rendered_msg_ids = desired_ids
        if was_at_bottom:
            self.scroll_to_bottom()

    def _find(self, msg_id: str) -> Optional[ChatMessage]:
        """Returns the message with *msg_id*, or None."""
        return next((m for m in self._read_context() if m.id == msg_id), None)

    def scroll_to_bottom(self) -> None:
        """Scrolls the log to the newest message."""
        self.scroll_end(animate=False)

    def _name_of_peer(self, frm: int) -> str:
        """What to call whoever said it, as the header writes it.

        A command is not a peer and is in no roster, so ``TOOL`` is named
        outright. A peer that has since gone — history reloaded from a backend
        outlives the connectors that filled it — falls back to its number,
        which is still true and still tells two of them apart.

        Args:
            frm: The id of whoever said it.

        Returns:
            str: The name, without the ``@``.
        """
        if frm == TOOL:
            return "tool"
        here = self._read_peers() if self._read_peers is not None else {}
        who  = here.get(frm)
        return name_of(who) if who is not None else str(frm)

    def _render_message(self, msg: ChatMessage) -> Widget:
        """Render a message as a clickable container with header and body."""
        prefix = "%s @%s · %s" % (
            msg.timestamp.strftime("%H:%M"), self._name_of_peer(msg.frm), msg.id,
        )
        if msg.reply_to is not None:
            prefix += " ↳ replying"

        header = Static(prefix, classes="message-header")
        parts: List[Widget] = []

        # Quote of the original message when this is a reply
        quote = None
        if msg.reply_to is not None:
            original = self._find(msg.reply_to)
            if original is not None:
                preview = " ".join(original.text.split())[:60]
                quote = f"↳ {original.id}: {preview}…"
                parts.append(Static(quote, classes="message-quote"))

        parts.append(Markdown(msg.text, classes="message-body"))

        bubble = Vertical(*parts, classes="message-bubble")
        # A bubble is as wide as its widest line and no wider, up to the
        # max-width the stylesheet sets, which Textual clamps this against.
        # It has to be measured here: `width: auto` collapses to nothing,
        # because Markdown reports no content width of its own.
        width = self._bubble_width(msg.text, quote, floor=len(prefix))
        bubble.styles.width = width

        # The header is a sibling of the bubble, and Textual's `align` shifts
        # the two as one block: a header left to size itself stays against the
        # bubble's *left* edge whichever side the block lands on, which on the
        # right is a whole bubble away from where the message is. So it takes
        # the bubble's own span, minus the border cell at each end, and the
        # stylesheet aligns the text inside it to the same side the bubble took.
        # A header too long for that keeps its own width, as it always did.
        header.styles.width = max(width - _HEADER_SLACK, len(prefix))

        # The header sits above the bubble rather than inside it, and the peer
        # class is on the container so one colour reaches both.
        container = _MessageContainer(
            header,
            bubble,
            msg_id=msg.id,
            on_select=self._on_message_clicked,
            on_copy=self.copy_message,
            classes="message-container %s" % self.style.header_class(msg.frm),
        )
        if msg.is_local:
            container.add_class("sent")
        else:
            container.add_class("received")

        self._msg_widgets[msg.id] = container
        return container

    def _bubble_width(self, text: str, quote: Optional[str] = None, floor: int = 0) -> int:
        """How wide this bubble wants to be, in cells.

        The widest line it has to show — the quote, or a line of the body —
        plus the bubble's own padding and border, and never narrower than the
        header above it. The whole thing is capped at ``bubble_max_width``,
        and the stylesheet's ``max-width: 100%`` is what keeps it inside a
        window narrower than that cap.

        Args:
            text: What the message says.
            quote: The reply preview, when this message answers another.
            floor: How wide the header is. The bubble is drawn under it, and a
                bubble narrower than its own header reads as two things rather
                than one; it takes ``_HEADER_SLACK`` more, so the two do not
                end flush.

        Returns:
            int: The width to set, borders and padding included.
        """
        lines  = text.splitlines() + ([quote] if quote else [])
        widest = max([len(line) for line in lines] + [0]) + _BUBBLE_CHROME
        return min(max(widest, floor + _HEADER_SLACK), self.style.bubble_max_width)

    def copy_message(self, msg_id: str) -> None:
        """Puts the message's text on the clipboard, by both routes at once.

        OSC 52 goes out immediately — it is one escape sequence — and a
        clipboard helper, if the system has one, runs in a worker because it
        is a subprocess and a chat must not stop for it. Neither route is
        enough alone: a terminal may drop OSC 52, and over SSH a helper writes
        a clipboard nobody is looking at.

        The notification names the routes that ran, rather than claiming the
        text arrived: whether it did is the terminal's business, and saying so
        plainly is what makes a silent failure diagnosable.
        """
        msg = self._find(msg_id)
        if msg is None:
            return
        self.app.copy_to_clipboard(msg.text)
        self.run_worker(self._copy_with_a_helper(msg.id, msg.text), exclusive=False)

    async def _copy_with_a_helper(self, msg_id: str, text: str) -> None:
        """Runs the clipboard helper off the event loop, then reports both routes."""
        loop  = asyncio.get_running_loop()
        route = await loop.run_in_executor(None, chat_clipboard.put, text)
        routes = "OSC 52" if route is None else "OSC 52 + %s" % route
        self.notify(
            "%s\n\nSent by %s." % (preview_of(text), routes),
            title   = "Copied %s" % msg_id,
            timeout = _CONFIRMATION,
        )

    # === Reply target (click) ======================================================

    def _on_message_clicked(self, msg_id: str) -> None:
        """Selects/deselects a message as the reply target."""
        if self.reply_target == msg_id:
            self.clear_reply_target()
        else:
            self.set_reply_target(msg_id)

    def set_reply_target(self, msg_id: str) -> None:
        """Marks *msg_id* as the reply target and highlights it."""
        self.reply_target = msg_id
        self._refresh_reply_target_ui()

    def clear_reply_target(self) -> None:
        """Clears the reply target and its highlight."""
        self.reply_target = None
        self._refresh_reply_target_ui()

    def _refresh_reply_target_ui(self) -> None:
        """Updates the visual highlight of all messages and notifies the app."""
        for msg_id, widget in self._msg_widgets.items():
            widget.set_class(msg_id == self.reply_target, "reply-target")
        if self._on_reply_target_change is not None:
            self._on_reply_target_change(self.reply_target)
