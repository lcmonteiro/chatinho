"""The same chat, without a terminal UI.

``ChatSession`` holds every use case — messages, command dispatch, connectors,
persistence — and imports no UI framework. The conversation itself is
protected: nothing here calls the session. ``Terminal`` below declares the
hooks it needs and the session hands the capabilities over at ``attach`` —
exactly what ``_Chat`` does, with the terminal taken out.

Note that ``import chatinho`` still loads Textual today, because the package's
``__init__`` eagerly imports the application. ``chatinho.chat_session`` itself
does not, and ``tests/test_architecture.py`` keeps it that way.

Run it:            python examples/headless.py
Feed it a script:  printf '/help\\nola\\n' | python examples/headless.py
"""

import sys
from typing import Any, Callable, Iterator, List

from chatinho import (
    ChatMessage,
    ChatSession,
    HelpCommand,
    HookAsk,
    HookExecute,
    HookLoadMessages,
    HookReceiveCommand,
    HookReceiveMessage,
    HookSay,
    HookSendCommand,
    HookSendMessage,
    command,
    connector,
    require,
)


@connector("echo")
@require(HookAsk)
@require(HookReceiveMessage)
@require(HookSay)
class EchoConnector:
    """Stands in for a real transport, and answers on its own.

    ``HookReceiveMessage`` tells it what entered the conversation; ``HookSay``
    gives it the way to write the answer back. It never imports the session.
    """

    say : Callable[..., str]

    def ask(self, message: str, **kwargs) -> str:
        """Returns the echoed answer instead of hitting the network."""
        return "Received: %s" % message

    def on_receive_message(self, msg: ChatMessage, **kwargs) -> None:
        """Answers what the user sent, and never its own answers."""
        if msg.is_sent_by_me:
            self.say(self.ask(msg.text), reply_to=msg.id)


@command("upper", "Upper-case the rest of the line")
@require(HookExecute)
class UpperCommand:
    """Command that shouts its arguments back."""

    def execute(self, *args, **kwargs) -> Any:
        """Returns the command's arguments in upper case."""
        arguments = kwargs.get("args", "")
        return arguments.upper() if arguments else "Usage: /upper <text>"


@require(HookSendMessage)
@require(HookSendCommand)
@require(HookLoadMessages)
@require(HookReceiveMessage)
@require(HookReceiveCommand)
class Terminal:
    """The presentation layer: prints what arrives, sends what is typed."""

    # Granted by the session at attach.
    send_message  : Callable[..., str]
    send_command  : Callable[[str], str]
    load_messages : Callable[..., List[ChatMessage]]

    def on_receive_message(self, msg: ChatMessage, **kwargs) -> None:
        """Renders one message on a plain terminal."""
        marker = ">" if msg.is_sent_by_me else "<"
        reply  = " (replying to %s)" % msg.reply_to if msg.reply_to else ""
        print("%s %s%s" % (marker, msg.text, reply))

    def on_receive_command(self, msg: ChatMessage, **kwargs) -> None:
        """Echoes the command line, before the session dispatches it."""
        print("> /%s" % msg.text)


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
        commands        = [HelpCommand(), UpperCommand()],
        command_handler = lambda command: print("? unknown command: /%s — try /help" % command),
    )
    # Hooks fire in registration order, and the echo answers re-entrantly: were
    # it registered first, its reply would print before the message it answers.
    view = Terminal()
    session.attach(view)
    session.add_connector(EchoConnector())

    print("Type a message, /help for commands, /quit to leave.")
    for line in read_lines():
        text = line.strip()
        if not text:
            continue
        if text in ("/quit", "/exit"):
            break
        if text.startswith("/"):
            view.send_command(text[1:].strip())
        else:
            view.send_message(text)

    session.close()
    print("--- %d messages, no terminal UI ---" % len(view.load_messages()))


if __name__ == "__main__":
    main()
