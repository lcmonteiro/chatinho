"""Demo of the chatinho library: markdown, code blocks, tools and replies.

Everything is built through the public ``create_chat`` factory. A tool is a
peer that can be asked, and a command is that ask: typing ``/code`` asks
the peer named "code".

Run with:  bash run.sh
"""

import asyncio

from chatinho import (
    ChatMessage,
    HelpCommand,
    HookExecute,
    HookListen,
    HookSay,
    Say,
    connector,
    create_chat,
    require,
    tool,
)


@connector("eco")
@require(HookListen)
@require(HookSay)
class EchoConnector:
    """Answers whatever the user says — a transport stand-in that talks back.

    ``HookListen`` is what tells it something was said; ``HookSay`` is what lets
    it reply. It never imports the session.
    """

    say : Say

    def __init__(self) -> None:
        #: The welcome message is the app talking, and the app *is* peer zero,
        #: so a connector cannot tell it from something the user typed. What a
        #: command writes it *can* tell apart — that is what TOOL is for.
        self._greeted = False

    async def listen(self, msg: ChatMessage) -> None:
        """Echoes the user, after a beat, without blocking the terminal."""
        if not msg.is_broadcast or not msg.is_local:
            return                      # a command wrote it, not the user
        if not self._greeted:
            self._greeted = True
            return
        await asyncio.sleep(0.6)
        await self.say("Received: _%s_" % msg.text, reply_to=msg.id)


@tool("code", "Show a Python code block")
@require(HookExecute)
@require(HookSay)
class CodeCommand:
    """Writes a Python code block, syntax-highlighted by the log.

    A command is seen only if it writes: ``HookSay`` is what puts its output in
    front of the user, and what it writes is not the user speaking.
    """

    say : Say

    async def execute(self, args: str = "", **kwargs) -> None:
        """Writes a Markdown code block."""
        await self.say(
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
    "Type `/` to see the commands:\n"
    "- `/help` — lists the tools\n"
    "- `/code` — shows an example with syntax highlighting\n\n"
    "Everything you type is rendered as Markdown, and the echo connector replies to it."
)


def main() -> None:
    """Builds the demo chat and runs it."""
    create_chat(
        connectors      = [EchoConnector()],
        commands        = [HelpCommand(), CodeCommand()],
        title           = "chatinho demo",
        welcome_message = WELCOME,
    ).run()


if __name__ == "__main__":
    main()
