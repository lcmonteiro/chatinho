"""The same chat, without a terminal UI.

``ChatSession`` routes messages between peers and imports no UI
framework. The conversation is protected: nothing here calls the session.
``Terminal`` below declares the hooks it needs and is registered at ``LOCAL``,
because the user is peer zero — exactly what ``ChatApp`` does, with the
terminal taken out.

Note that ``import chatinho`` still loads Textual today, because the package's
``__init__`` eagerly imports the application. ``chatinho.chat_session`` itself
does not, and ``tests/test_architecture.py`` keeps it that way.

Run it:            python examples/headless.py
Feed it a script:  printf '/help\\nola\\n' | python examples/headless.py
"""

import asyncio
import sys
from typing import List, Optional

from chatinho import (
    LOCAL,
    Ask,
    ChatMessage,
    ChatSession,
    HelpCommand,
    HookAsk,
    HookContext,
    HookExecute,
    HookAnswer,
    HookListen,
    HookInvoke,
    HookPeers,
    HookSay,
    Context,
    Invoke,
    Peers,
    Say,
    connector,
    require,
    tool,
)


@connector("eco")
@require(HookListen)
@require(HookSay)
class EchoConnector:
    """Answers whatever is said to everyone, and never its own answers.

    A sender does not hear its own broadcast, which is what stops this from
    answering itself forever.
    """

    say : Say

    async def listen(self, msg: ChatMessage) -> None:
        """Replies to what the user said — not to what a command wrote."""
        if not msg.is_broadcast or not msg.is_local:
            return
        await self.say("Received: %s" % msg.text, reply_to=msg.id)


@tool("upper", "Upper-case the rest of the line")
@require(HookExecute)
class UpperCommand:
    """Shouts its arguments back.

    A command is not a peer: it has no id, nothing is addressed to it, and it
    runs only when someone runs it.
    """

    async def execute(self, args: str = "", **kwargs) -> str:
        """Answers with the arguments in upper case.

        Answering is what puts it in the conversation: saying it too would
        write the same line twice.
        """
        return args.upper() if args else "Usage: /upper <text>"


@connector("terminal", id=LOCAL)
@require(HookSay)
@require(HookAsk)
@require(HookListen)
@require(HookAnswer)
@require(HookContext)
@require(HookPeers)
@require(HookInvoke)
class Terminal:
    """The presentation layer: prints what arrives, sends what is typed."""

    # Granted by the session at attach.
    say           : Say
    ask           : Ask
    context : Context
    peers         : Peers
    invoke        : Invoke

    async def listen(self, msg: ChatMessage) -> None:
        """Renders one broadcast on a plain terminal."""
        reply = " (replying to %s)" % msg.reply_to if msg.reply_to else ""
        print("< %s%s" % (msg.text, reply))

    async def answer(self, msg: ChatMessage) -> Optional[str]:
        """Shows a question put to the user; the reply is theirs to type."""
        print("? %s  — reply with  =<answer>" % msg.text)
        return None

    async def serve(self) -> None:
        """Reads stdin until it ends, and that is the end of the chat.

        Lifecycle, not a hook: ``ChatSession.run()`` runs this and closes when
        it returns. No ``asyncio.run`` here and no ``start``/``close`` — the
        session owns all three.
        """
        print("Type a message, /help for commands, /quit to leave.")
        for line in await read_lines():
            text = line.strip()
            if not text or text in ("/quit", "/exit"):
                break
            if text.startswith("/"):
                await self.command(text[1:].strip())
            else:
                print("> %s" % text)
                await self.say(text)
                # Nothing blocks here: the echo answers on its own queue, so
                # give the loop a moment before reading the next line.
                await asyncio.sleep(0.05)
        print("--- %d messages, no terminal UI ---" % len(self.context()))

    async def command(self, line: str) -> None:
        """Runs ``/name args``.

        Nothing is printed here on success: a command that should be seen wrote
        its own output, and ``listen`` rendered it like anything else. The
        answer comes back for the caller, which here has no use for it.
        """
        name, _, args = line.partition(" ")
        if await self.invoke(name, args.strip()) is None:
            print("? unknown command: /%s — try /help" % name)
        await asyncio.sleep(0.05)


async def read_lines() -> List[str]:
    """Reads stdin off the event loop, so nothing blocks while we wait."""
    return await asyncio.get_running_loop().run_in_executor(None, sys.stdin.readlines)


def main() -> None:
    """Builds a headless chat and lets the session run it."""
    # The terminal is a connector like any other: it declares the id it can
    # only be — LOCAL, because it speaks for the person — and the session
    # numbers the rest. Registration order matters: hooks fire in it, and the
    # echo answers re-entrantly, so the terminal listening first keeps the
    # reply below the message it answers.
    ChatSession(
        connectors = [Terminal(), EchoConnector()],
        commands   = [HelpCommand(), UpperCommand()],
    ).run()


if __name__ == "__main__":
    main()
