"""ChatStyle: programmatic style builder for chatinho.

Build the chat UI theme in Python instead of editing raw CSS:

    from chatinho import ChatStyle, build_chat

    style = ChatStyle(accent="#ff5733", sent_bubble_border="#ff5733")
    chat = build_chat(style=style)

Use ``dataclasses.replace`` to tweak a base style without touching the rest:

    from dataclasses import replace

    dark = ChatStyle()
    green = replace(dark, accent="#00ff88")

**The default palette is Claude Code's**: a warm neutral ramp from
``#1f1e1d`` up to the ``#f0eee6`` cream it writes on, with Claude's own
``#d97757`` as the accent, and the rest of that terminal's colours —
periwinkle, green, amber, pink — spread across the peer slots.

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
    /* No padding on the right: a scrollbar is inset by it, and this is what
       puts the bar against the edge. What keeps a bubble off the bar is its
       own `bubble_margin_right`, which is now the only thing doing it. */
    padding: 1 0 1 2;
    background: $chat_bg;
}
/* Both scrollables in one rule, so the log's bar and the input's cannot
   drift apart. The input is a TextArea with a bar of its own, and it wore
   Textual's blue at two cells wide until it was named here — the same
   silence the dead `.scrollbar` rule used to keep. */
#chat-log, #input-line {
    scrollbar-size-vertical: $scrollbar_size;
    scrollbar-background: $scrollbar_bg;
    scrollbar-color: $scrollbar_color;
    scrollbar-background-hover: $scrollbar_hover_bg;
    scrollbar-color-hover: $scrollbar_hover_color;
    scrollbar-background-active: $scrollbar_hover_bg;
    scrollbar-color-active: $scrollbar_hover_color;
    scrollbar-corner-color: $chat_bg;
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
/* The popup never takes focus — the input keeps it — so Textual draws the
   highlighted row with its *blurred* block cursor, which is the theme's blue
   and not ours. Both states are set, or the palette holds everywhere except
   the one row the eye is on. */
#command-suggestions > .option-list--option-highlighted,
#command-suggestions:focus > .option-list--option-highlighted {
    background: $accent;
    color: $screen_bg;
    text-style: bold;
}
/* The copy confirmation is Textual's own widget, floated above the chat;
   without this it arrives in the default theme's colours. Warning and error
   keep theirs, which mean something. */
Toast {
    background: $input_bg;
    color: $input_color;
}
Toast.-information {
    border-left: outer $accent;
}
Toast.-information .toast--title {
    color: $accent;
}
#input-line {
    height: auto;
    max-height: $input_max_height;
    /* Right padding zeroed for the same reason the log's is: it is what the
       bar is inset by, and both have to land in the same column. */
    padding: 0 0 0 1;
    background: transparent;
    color: $input_color;
}
$input_frame_rules
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
    max-width: 100%;
    text-style: bold;
    margin: 0 0 0 1;
}
/* ChatLog gives the header the bubble's own span, so the text inside it can
   take the side the bubble took. Without this the header sits against the
   bubble's left edge on both sides, because `align` moves the pair as one
   block and does not align within it. */
.message-container.sent .message-header {
    text-align: $local_align;
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

    Every colour field is a hex string; the size fields are Textual lengths
    (cells, or a percentage), except ``scrollbar_size``, which Textual takes
    only as a whole number of cells. ``to_css()`` turns the values into a
    Textual stylesheet by rendering the module-level ``_CSS_TEMPLATE``.
    """

    # Screen / layout
    screen_bg: str = "#1f1e1d"
    chat_bg: str = "#1f1e1d"

    # Scrollbar. Textual draws it two cells wide by default, which is a wide
    # thing to give up beside a chat that is mostly margin already; one cell
    # still reads as a bar and still takes a drag, and one cell is the floor —
    # a terminal cannot reserve less, and Textual refuses a width below it.
    #
    # What the cell is *painted* with is the other half. The track is
    # `transparent` rather than a colour of its own, so at rest the bar is the
    # thumb alone and the column behind it is chat: Textual composites a
    # translucent scrollbar background onto the parent's, so this follows
    # `chat_bg` wherever it goes instead of repeating its hex. The hover and
    # active colours below are unchanged, so the track comes back the moment
    # the pointer reaches for it.
    scrollbar_size: int = 1
    scrollbar_bg: str = "transparent"
    scrollbar_color: str = "#8a8984"
    scrollbar_hover_bg: str = "#3d3b37"
    scrollbar_hover_color: str = "#f0eee6"

    # Input line — it grows with the text up to this many rows.
    #
    # `input_frame` is how it is drawn: "lines" rules it off above and below
    # and leaves the sides open, "box" puts the rounded border back on all
    # four. Two lines give the text the two columns the sides were taking,
    # which is the whole width on a phone, and read as somewhere to write
    # rather than as a widget sitting in the chat.
    input_frame: str = "lines"
    input_bg: str = "#262624"
    input_border: str = "#3d3b37"
    input_color: str = "#f0eee6"
    # Brighter than the resting rule, not a different hue: the accent outlined
    # a box the size of a widget, and as two rules across the whole width it
    # was two orange bars over a chat that has none anywhere else. Focus does
    # leave the input — Tab moves it to the log — so the two states still have
    # to differ; brightness is enough to say which one it is.
    input_focus_border: str = "#8a8984"
    input_max_height: str = "8"

    # Accent (quote border)
    accent: str = "#d97757"

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
    local_align: str = "right"

    # One colour per peer: the header — who spoke, and the message id — and
    # the bubble's border beneath it, so a peer is one colour and not two.
    # Indexed by the peer's id, and wrapped round when there are more peers
    # than colours; slot zero is the user, and a command speaks as TOOL.
    peer_headers: Tuple[str, ...] = (
        "#e5e4df",       # 0 — LOCAL, the user: Claude Code writes your own
                         #     turn in plain cream, and so does this
        "#d97757",       # 1 — Claude's orange. The hues are spread apart on
                         #     purpose: the common chat is the user and one
                         #     connector, so slots 0 and 1 have to be told
                         #     apart at a glance — two greens were not, and
                         #     cream against orange is the pairing Claude
                         #     Code itself reads as "you" and "them"
        "#b1b9f9",       # periwinkle
        "#4eba65",       # green
        "#ffc107",       # amber
        "#fd5db1",       # pink
    )
    # A command is not a peer, and Claude Code dims its tool lines rather than
    # giving them a voice; the warm grey says machinery, not somebody speaking.
    tool_header: str = "#8a8984"

    # Sent bubbles — the border is what is drawn; the bg is the reply-target tint
    sent_bubble_bg: str = "#3d3b37"
    sent_text: str = "#f0eee6"

    # Received bubbles — the border is what is drawn; the bg is the reply-target tint
    received_bubble_bg: str = "#2f2e2b"
    received_text: str = "#f0eee6"

    # Quote (reply preview)
    quote_color: str = "#8a8984"
    quote_bg: str = "#262624"

    def __post_init__(self) -> None:
        """Refuses a palette with nothing in it, a side or a frame that is neither, and a bar of no width.

        Raises:
            ValueError: ``peer_headers`` is empty, which would leave the
                header with no colour and the modulo with no divisor;
                ``local_align`` is not a side or ``input_frame`` is neither
                shape, which Textual would take as a broken rule and report
                nowhere the caller would look; or
                ``scrollbar_size`` is not a whole number of cells above zero,
                which Textual refuses too — but at mount, pointing at the
                stylesheet this generated rather than at the field it came
                from.
        """
        if not self.peer_headers:
            raise ValueError("peer_headers needs at least one colour")
        if self.local_align not in ("left", "right"):
            raise ValueError(
                "local_align is a side: 'left' or 'right', not %r" % (self.local_align,)
            )
        if self.input_frame not in ("lines", "box"):
            raise ValueError(
                "input_frame is 'lines' or 'box', not %r" % (self.input_frame,)
            )
        if not isinstance(self.scrollbar_size, int) or isinstance(self.scrollbar_size, bool) \
           or self.scrollbar_size < 1:
            raise ValueError(
                "scrollbar_size is a width in cells, one or more, not %r" % (self.scrollbar_size,)
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
            input_frame_rules=self._input_frame_rules(),
            **asdict(self),
        )

    def _input_frame_rules(self) -> str:
        """The border declarations for the input, resting and focused.

        They are computed rather than written into the template because the
        two shapes do not differ by a value: a box sets one `border`, and two
        rules have to clear it and set `border-top` and `border-bottom`
        instead — a rule left in place would override them, the declaration
        coming later in the block.

        Returns:
            str: The `#input-line` and `#input-line:focus` rules.
        """
        def framed(colour: str) -> str:
            if self.input_frame == "box":
                return "    border: round %s;" % colour
            return ("    border: none;\n"
                    "    border-top: solid %s;\n"
                    "    border-bottom: solid %s;" % (colour, colour))

        return "#input-line {\n%s\n}\n#input-line:focus {\n%s\n}" % (
            framed(self.input_border), framed(self.input_focus_border),
        )
