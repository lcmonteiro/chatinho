"""Demo of the chatinho library: shows markdown, code blocks, commands,
replies and command autocomplete.

Everything is built through the public ``create_chat`` factory: a connector
stands in for a transport, commands are registered objects, and the bot
replies by sending the message back through the connector.

Run with:  bash run.sh
"""

from typing import Any, Optional

from chatinho import BaseCommand, BaseConnector, ChatMessage, HelpCommand, create_chat


class EchoConnector(BaseConnector):
    """Connector that echoes what it is given — stands in for a real transport."""

    def __init__(self) -> None:
        super().__init__(name="echo")

    def initialize(self) -> None:
        """Nothing to set up: the echo is local."""

    def send(self, message: str, **kwargs) -> str:
        """Returns the echoed answer instead of hitting the network."""
        return f"Received: _{message}_"

    def receive(self, **kwargs) -> Optional[str]:
        """The echo is synchronous, so there is nothing to poll for."""
        return None


class CodeCommand(BaseCommand):
    """Command that shows a Python code block with syntax highlighting."""

    def __init__(self) -> None:
        super().__init__(name="code", description="Show a Python code block")

    def execute(self, *args, **kwargs) -> Any:
        """Returns a Markdown code block."""
        return (
            "Here is an example with **syntax highlighting**:\n\n"
            "```python\n"
            "def fib(n: int) -> int:\n"
            "    a, b = 0, 1\n"
            "    for _ in range(n):\n"
            "        a, b = b, a + b\n"
            "    return a\n"
            "```"
        )


WELCOME = (
    "Welcome to **chatinho**! 👋\n\n"
    "You can send commands — type `/` to see suggestions:\n"
    "- `/help` — lists the registered commands\n"
    "- `/code` — shows an example with syntax highlighting\n\n"
    "Everything you type is rendered as Markdown, and the echo connector replies to it."
)


def main() -> None:
    """Builds the demo chat and runs it."""
    chat = create_chat(
        connectors      = [EchoConnector()],
        commands        = dict(
            help = HelpCommand(),
            code = CodeCommand(),
        ),
        title           = "chatinho demo",
        welcome_message = WELCOME,
    )

    def echo_reply(msg: ChatMessage) -> None:
        """Sends each message through the connector and shows the answer.

        Uses set_timer instead of time.sleep so the UI thread is never
        blocked: the sent message paints immediately, and the reply lands
        0.6s later without freezing the app.
        """
        if msg.is_command:
            return
        answer = chat.send_message_via_connector("echo", msg.text)
        chat.set_timer(0.6, lambda: chat.receive_message(answer, reply_to=msg.id))

    chat.on_message_sent = echo_reply  # type: ignore[method-assign]
    chat.run()


if __name__ == "__main__":
    main()
