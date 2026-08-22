"""ChatStyle: programmatic style builder for chatinho.

Build the chat UI theme in Python instead of editing raw CSS:

    from chatinho import ChatApp, ChatStyle

    style = ChatStyle(accent="#ff5733", sent_bubble_bg="#1a4d3a")
    app = ChatApp(style=style)

Use ``dataclasses.replace`` to tweak a base style without touching the rest:

    from dataclasses import replace

    dark = ChatStyle()
    green = replace(dark, accent="#00ff88")
"""

from dataclasses import asdict, dataclass
from string import Template

# Template first: the stylesheet with $placeholders for every ChatStyle field.
_CSS_TEMPLATE = Template(
    """
Screen {
    layout: vertical;
    background: $screen_bg;
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
    height: 3;
    background: $input_bg;
    border: round $input_border;
    color: $input_color;
}
#input-line:focus {
    border: round $input_focus_border;
}
.message-container {
    layout: horizontal;
    width: 100%;
    padding: 0 0 1 0;
    height: auto;
}
.message-container.reply-target .message-bubble {
    outline: thick $accent;
}
.message-container.sent {
    align: right top;
}
.message-container.received {
    align: left top;
}
.message-bubble {
    layout: vertical;
    max-width: 90%;
    padding: 1 2;
    border: round $received_bubble_border;
    background: $received_bubble_bg;
    color: $received_text;
    height: auto;
}
.message-container.sent .message-bubble {
    background: $sent_bubble_bg;
    border: round $sent_bubble_border;
    color: $sent_text;
}
.message-container.received .message-bubble {
    background: $received_bubble_bg;
    border: round $received_bubble_border;
    color: $received_text;
}
.message-header {
    color: $received_header;
    text-style: bold;
    margin: 0;
}
.message-container.sent .message-header {
    color: $sent_header;
}
.message-body {
    margin: 0;
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

    Every field is a hex colour string; defaults reproduce the classic
    chatlib look. ``to_css()`` turns the values into a Textual stylesheet
    by rendering the module-level ``_CSS_TEMPLATE``.
    """

    # Screen / layout
    screen_bg: str = "#0b141a"
    chat_bg: str = "#0b141a"

    # Scrollbar
    scrollbar_bg: str = "#1f2c33"
    scrollbar_color: str = "#8696a0"
    scrollbar_hover_bg: str = "#2a3942"
    scrollbar_hover_color: str = "#e9edef"

    # Input line
    input_bg: str = "#202c33"
    input_border: str = "#2a3942"
    input_color: str = "#e9edef"
    input_focus_border: str = "#00a884"

    # Accent (reply outline + quote border)
    accent: str = "#00a884"

    # Sent bubbles
    sent_bubble_bg: str = "#005c4b"
    sent_bubble_border: str = "#005c4b"
    sent_text: str = "#e9edef"
    sent_header: str = "#8fd6b4"

    # Received bubbles
    received_bubble_bg: str = "#202c33"
    received_bubble_border: str = "#202c33"
    received_text: str = "#e9edef"
    received_header: str = "#7de0a3"

    # Quote (reply preview)
    quote_color: str = "#8696a0"
    quote_bg: str = "#111b21"

    def to_css(self) -> str:
        """Render this style as a Textual CSS string."""
        return _CSS_TEMPLATE.substitute(**asdict(self))
