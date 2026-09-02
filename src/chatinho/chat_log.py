"""The scrollable chat log and the message bubbles it mounts.

:class:`ChatLog` owns its own children: which messages are currently rendered,
their widgets, and which one is selected as the reply target. The application
only tells it when the history changed.
"""

import logging
from typing import Callable, Dict, List, Optional

from textual import events
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.widget import Widget
from textual.widgets import Markdown, Static

from .chat_message import ChatMessage

logger = logging.getLogger(__name__)


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


class _MessageContainer(Horizontal):
    """Clickable message container — selects the msg as a reply target."""

    def __init__(
        self,
        *children: Widget,
        msg_id: str,
        on_select: Callable[[str], None],
        **kwargs,
    ) -> None:
        super().__init__(*children, **kwargs)
        self.msg_id = msg_id
        self._on_select = on_select

    def on_click(self, event: events.Click) -> None:
        self._on_select(self.msg_id)
        event.stop()


class ChatLog(TouchScrollableContainer):
    """Renders the last ``max_displayed`` messages the chat will hand over.

    Reads through ``load_messages`` — the capability the presentation was
    granted — rather than holding the history itself. Messages leaving the
    window are unmounted from the terminal, not forgotten.
    """

    def __init__(
        self,
        load_messages : Callable[..., List[ChatMessage]],
        max_displayed : int = 100,
        on_reply_target_change : Optional[Callable[[Optional[str]], None]] = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._load_messages = load_messages
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

        desired_ids = [m.id for m in self._load_messages(limit=self.max_displayed)]
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
        return next((m for m in self._load_messages() if m.id == msg_id), None)

    def scroll_to_bottom(self) -> None:
        """Scrolls the log to the newest message."""
        self.scroll_end(animate=False)

    def _render_message(self, msg: ChatMessage) -> Widget:
        """Render a message as a clickable container with header and body."""
        sender = "You" if msg.is_sent_by_me else "Other"
        time_str = msg.timestamp.strftime("%H:%M")
        prefix = f"[{time_str}] {sender} · {msg.id}"
        if msg.reply_to is not None:
            prefix += " ↳ replying"

        header = Static(prefix, classes="message-header")
        parts: List[Widget] = [header]

        # Quote of the original message when this is a reply
        if msg.reply_to is not None:
            original = self._find(msg.reply_to)
            if original is not None:
                preview = " ".join(original.text.split())[:60]
                parts.append(
                    Static(f"↳ {original.id}: {preview}…", classes="message-quote")
                )

        parts.append(Markdown(msg.text, classes="message-body"))

        bubble = Vertical(*parts, classes="message-bubble")

        # Clickable container — aligns left/right and selects the reply target
        container = _MessageContainer(
            bubble,
            msg_id=msg.id,
            on_select=self._on_message_clicked,
            classes="message-container",
        )
        if msg.is_sent_by_me:
            container.add_class("sent")
        else:
            container.add_class("received")

        self._msg_widgets[msg.id] = container
        return container

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
