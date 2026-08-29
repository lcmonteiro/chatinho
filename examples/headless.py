"""The same chat, without a terminal UI.

``ChatSession`` holds every use case — messages, command dispatch, connectors,
persistence — and imports no UI framework. Here it is wired to stdin/stdout
instead of Textual; ``examples/demo.py`` wires the same object to a TUI.

Note that ``import chatinho`` still loads Textual today, because the package's
``__init__`` eagerly imports the application. ``chatinho.chat_session`` itself
does not, and ``tests/test_architecture.py`` keeps it that way.

Run it:            python examples/headless.py
Feed it a script:  printf '/help\\nola\\n' | python examples/headless.py
"""

import sys
from typing import Any, Iterator

from chatinho import BaseCommand, BaseConnector, ChatMessage, ChatSession, HelpCommand


class EchoConnector(BaseConnector):
    """Stands in for a real transport: echoes whatever it is given."""

    def __init__(self) -> None:
        super().__init__(name="echo")

    def initialize(self) -> None:
        """Nothing to set up: the echo is local."""

    def ask(self, message: str, **kwargs) -> str:
        """Returns the echoed answer instead of hitting the network."""
        return f"Received: {message}"


class UpperCommand(BaseCommand):
    """Command that shouts its arguments back."""

    def __init__(self) -> None:
        super().__init__(name="upper", description="Upper-case the rest of the line")

    def execute(self, *args, **kwargs) -> Any:
        """Returns the command's arguments in upper case."""
        arguments = kwargs.get("args", "")
        return arguments.upper() if arguments else "Usage: /upper <text>"


def render(msg: ChatMessage) -> str:
    """Formats a message for a plain terminal."""
    marker = ">" if msg.is_sent_by_me else "<"
    reply = f" (replying to {msg.reply_to})" if msg.reply_to else ""
    return f"{marker} {msg.text}{reply}"


def read_lines() -> Iterator[str]:
    """Yields input lines, prompting only when there is someone to prompt."""
    if sys.stdin.isatty():
        while True:
            try:
                yield input("chatinho> ")
            except EOFError:
                return
    else:
        for line in sys.stdin:
            yield line


def main() -> None:
    """Builds a headless chat and drives it from stdin."""
    session = ChatSession(
        connectors = [EchoConnector()],
        commands   = dict(
            help  = HelpCommand(),
            upper = UpperCommand(),
        ),
    )

    # The presentation layer, in one line: print whatever enters the history.
    session.on_message_added = lambda msg: print(render(msg))
    session.command_handler = lambda command: session.receive_message(
        f"Unknown command: /{command} — try /help"
    )

    def echo_reply(msg: ChatMessage) -> None:
        """Sends each message through the connector and shows the answer."""
        if msg.is_command:
            return
        session.receive_message(session.ask_connector("echo", msg.text), reply_to=msg.id)

    session.on_message_sent = echo_reply

    print("Type a message, /help for commands, /quit to leave.")
    for line in read_lines():
        text = line.strip()
        if not text:
            continue
        if text in ("/quit", "/exit"):
            break
        if text.startswith("/"):
            session.send_command(text[1:].strip())
        else:
            session.send_message(text)

    print(f"--- {len(session.messages)} messages, no terminal UI ---")


if __name__ == "__main__":
    main()
