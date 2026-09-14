"""The scrollable chat log and the message bubbles it mounts.

:class:`ChatLog` owns its own children: which messages are currently rendered,
their widgets, and which one is selected as the reply target. The application
only tells it when the history changed.
"""

import logging
import time
from typing import Callable, Dict, List, Optional

from textual import events
from textual.containers import ScrollableContainer, Vertical
from textual.widget import Widget
from textual.widgets import Markdown, Static

from .chat_hooks import name_of
from .chat_message import TOOL, ChatMessage
from .chat_style import ChatStyle

logger = logging.getLogger(__name__)

#: What a bubble costs around its text: `padding: 1 2` either side, plus the
#: two cells its `border: round` draws in. The stylesheet zeroes `Markdown`'s
#: own `padding: 0 2 0 2` so it is not four more that this does not count —
#: a line measured to fit would otherwise wrap.
_BUBBLE_CHROME : int = 6

#: How long a press has to be held before it copies rather than selects.
#: Long enough not to fire on a tap, short enough not to feel stuck.
_LONG_PRESS : float = 0.5

#: How far a press may wander and still count as a press rather than a drag.
#: One row of slack: a finger on a phone screen is never perfectly still.
_A_DRAG : int = 1

#: What a bubble adds to its header's width to sit under it: the header's own
#: `margin-left`, plus one space so the two do not end flush.
_HEADER_SLACK : int = 2


class TouchScrollableContainer(ScrollableContainer):
    """Scrollable container that supports mouse/touch drag scrolling."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._drag_start_y: int = 0
        self._scroll_start_y: int = 0

    def on_mouse_down(self, event: events.MouseDown) -> None:
        """Record the start position when drag begins."""
        self._drag_start_y = event.y
        self._scroll_start_y = self.scroll_offset.y
        event.stop()

    def on_mouse_move(self, event: events.MouseMove) -> None:
        """Handle drag to scroll vertically."""
        if not event.button:
            return
        delta_y = event.y - self._drag_start_y
        target_y = self._scroll_start_y - delta_y
        max_y = self.max_scroll_y
        if max_y > 0:
            target_y = max(0, min(target_y, max_y))
            self.scroll_to(y=target_y, animate=False)
        event.stop()

    def on_mouse_up(self, event: events.MouseUp) -> None:
        """Handle drag end."""
        event.stop()


class _MessageContainer(Vertical):
    """One message: its header, the bubble under it, and what a press means.

    A short press selects the message as the reply target; a press held for
    :data:`_LONG_PRESS` copies its text instead.
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
        self._pressed_at : Optional[float] = None
        self._pressed_y  : int = 0

    def on_mouse_down(self, event: events.MouseDown) -> None:
        """Starts the clock, and remembers where the press landed.

        Deliberately does not stop the event: the log scrolls by dragging, and
        that reads the same mouse events, so a message that swallowed them
        would be a message you could not scroll past.
        """
        self._pressed_at = time.monotonic()
        self._pressed_y  = event.screen_y

    def on_mouse_up(self, event: events.MouseUp) -> None:
        """Copies a press that was held, selects a tap, and ignores a drag.

        Decided here rather than in ``on_click`` because a click carries no
        duration: Textual synthesises it from the press and the release, and
        by then how long it took is gone.
        """
        pressed_at, pressed_y = self._pressed_at, self._pressed_y
        self._pressed_at = None
        if pressed_at is None:
            return                      # the press began somewhere else
        if abs(event.screen_y - pressed_y) > _A_DRAG:
            return                      # the log was being scrolled, not tapped
        if time.monotonic() - pressed_at >= _LONG_PRESS:
            self._on_copy(self.msg_id)
        else:
            self._on_select(self.msg_id)


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
        bubble.styles.width = self._bubble_width(msg.text, quote, floor=len(prefix))


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
        """Puts the message's text on the clipboard, and says so.

        Whether it arrives depends on the terminal: this is OSC 52, which a
        terminal may refuse or not implement. The notification says what was
        attempted, not that it landed.
        """
        msg = self._find(msg_id)
        if msg is None:
            return
        self.app.copy_to_clipboard(msg.text)
        self.notify("Copied %s" % msg.id, timeout=2)

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
