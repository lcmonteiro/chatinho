"""ChatStyle: programmatic style builder for chatinho.

Build the chat UI theme in Python instead of editing raw CSS:

    from chatinho import ChatStyle, build_chat

    style = ChatStyle(accent="#ff5733", sent_bubble_border="#ff5733")
    chat = build_chat(style=style)

Use ``dataclasses.replace`` to tweak a base style without touching the rest:

    from dataclasses import replace

    dark = ChatStyle()
    green = replace(dark, accent="#00ff88")

**A bubble is drawn as an outline, not as a fill.** The border carries the
colour and the chat background shows through, so the two ``*_bubble_bg``
fields are the tint a bubble takes *only* while it is the reply target —
selection is the one thing a filled background means.
"""

from dataclasses import asdict, dataclass
from string import Template
from typing import Tuple

from .chat_message import TOOL

# Template first: the stylesheet with $placeholders for every ChatStyle field.
_CSS_TEMPLATE = Template(
    """
Screen {
    layout: vertical;
    align-horizontal: center;
    background: $screen_bg;
}
#chat-body {
    width: 100%;
    max-width: $chat_max_width;
    height: 1fr;
}
#chat-log {
    height: 1fr;
    overflow-y: auto;
    padding: 1 2;
    background: $chat_bg;
}
.scrollbar {
    background: $scrollbar_bg;
    color: $scrollbar_color;
}
.scrollbar:hover {
    background: $scrollbar_hover_bg;
    color: $scrollbar_hover_color;
}
#input-area {
    dock: bottom;
    height: auto;
}
#command-suggestions {
    display: none;
    height: auto;
    max-height: 8;
    background: $input_bg;
    border: round $input_border;
    color: $input_color;
}
#command-suggestions.-visible {
    display: block;
}
#input-line {
    height: auto;
    max-height: $input_max_height;
    padding: 0 1;
    background: transparent;
    border: round $input_border;
    color: $input_color;
}
#input-line:focus {
    border: round $input_focus_border;
}
.message-container {
    layout: vertical;
    width: 100%;
    padding: 0 0 1 0;
    margin: 0 $bubble_margin_right 0 0;
    height: auto;
    align: left top;
}
.message-container.sent {
    align: $local_align top;
}
.message-bubble {
    layout: vertical;
    width: auto;
    max-width: 100%;
    padding: 1 2;
    background: transparent;
    color: $received_text;
    height: auto;
}
.message-container.sent .message-bubble {
    color: $sent_text;
}
.message-container.received .message-bubble {
    color: $received_text;
}
.message-container.sent.reply-target .message-bubble {
    background: $sent_bubble_bg;
}
.message-container.received.reply-target .message-bubble {
    background: $received_bubble_bg;
}
.message-header {
    width: auto;
    text-style: bold;
    margin: 0 0 0 1;
}
$peer_header_rules
.message-body {
    margin: 0;
    padding: 0;
}
.message-body > *:last-child {
    margin-bottom: 0;
}
.message-quote {
    color: $quote_color;
    background: $quote_bg;
    border-left: thick $accent;
    padding: 0 1;
    margin: 0 0 1 0;
}
"""
)


@dataclass(frozen=True)
class ChatStyle:
    """Theme colours for the chat UI.

    Every colour field is a hex string; the two size fields are Textual
    lengths (cells, or a percentage). ``to_css()`` turns the values into a
    Textual stylesheet by rendering the module-level ``_CSS_TEMPLATE``.
    """

    # Screen / layout
    screen_bg: str = "#0b141a"
    chat_bg: str = "#0b141a"

    # Scrollbar
    scrollbar_bg: str = "#1f2c33"
    scrollbar_color: str = "#8696a0"
    scrollbar_hover_bg: str = "#2a3942"
    scrollbar_hover_color: str = "#e9edef"

    # Input line — drawn as an outline; it grows with the text up to this many rows
    input_bg: str = "#202c33"
    input_border: str = "#2a3942"
    input_color: str = "#e9edef"
    input_focus_border: str = "#00a884"
    input_max_height: str = "8"

    # Accent (quote border)
    accent: str = "#00a884"

    # How wide a bubble may grow before its text wraps, and how far its right
    # edge stays clear of the scrollbar. The width is applied in Python, by
    # ChatLog, because only it knows how wide the text actually is.
    bubble_max_width: int = 72
    bubble_margin_right: str = "2"

    # How wide the chat itself may grow. It is centred in whatever is left
    # over, so a wide terminal gives margins rather than lines too long to
    # read across.
    chat_max_width: str = "100"

    # Which side the user's own messages sit on: "left" or "right". Everyone
    # else is always on the left, so "right" makes the conversation read as
    # two columns and "left" as one.
    local_align: str = "left"

    # One colour per peer: the header — who spoke, and the message id — and
    # the bubble's border beneath it, so a peer is one colour and not two.
    # Indexed by the peer's id, and wrapped round when there are more peers
    # than colours; slot zero is the user, and a command speaks as TOOL.
    peer_headers: Tuple[str, ...] = (
        "#8fd6b4",       # 0 — LOCAL, the user
        "#f6c177",       # the hues are spread apart on purpose: the common
        "#9ccfd8",       # chat is the user and one connector, so slots 0 and
        "#c4a7e7",       # 1 have to be told apart at a glance — two greens
        "#eb6f92",       # were not
        "#7de0a3",
    )
    tool_header: str = "#b8a1e3"

    # Sent bubbles — the border is what is drawn; the bg is the reply-target tint
    sent_bubble_bg: str = "#005c4b"
    sent_text: str = "#e9edef"

    # Received bubbles — the border is what is drawn; the bg is the reply-target tint
    received_bubble_bg: str = "#202c33"
    received_text: str = "#e9edef"

    # Quote (reply preview)
    quote_color: str = "#8696a0"
    quote_bg: str = "#111b21"

    def __post_init__(self) -> None:
        """Refuses a palette with nothing in it, and a side that is neither.

        Raises:
            ValueError: ``peer_headers`` is empty, which would leave the
                header with no colour and the modulo with no divisor; or
                ``local_align`` is not a side, which Textual would take as a
                broken rule and report nowhere the caller would look.
        """
        if not self.peer_headers:
            raise ValueError("peer_headers needs at least one colour")
        if self.local_align not in ("left", "right"):
            raise ValueError(
                "local_align is a side: 'left' or 'right', not %r" % (self.local_align,)
            )

    def header_class(self, frm: int) -> str:
        """The header class carrying *frm*'s colour.

        A command is not a peer and has no id of its own, so ``TOOL`` gets a
        name rather than a slot. Every other id wraps round the palette.

        Args:
            frm: The id of whoever said it.

        Returns:
            str: The class name, matching a rule ``to_css()`` wrote.
        """
        if frm == TOOL:
            return "peer-tool"
        return "peer-%d" % (frm % len(self.peer_headers))

    def to_css(self) -> str:
        """Render this style as a Textual CSS string."""
        rules = []
        for slot, colour in list(enumerate(self.peer_headers)) + [("tool", self.tool_header)]:
            at = "peer-%s" % slot
            rules.append(".message-container.%s .message-header {\n    color: %s;\n}" % (at, colour))
            rules.append(
                ".message-container.%s .message-bubble {\n    border: round %s;\n}" % (at, colour)
            )
        return _CSS_TEMPLATE.substitute(
            peer_header_rules="\n".join(rules),
            **asdict(self),
        )
