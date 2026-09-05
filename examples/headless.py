"""The same chat, without a terminal UI.

``ChatSession`` routes messages between peers and imports no UI
framework. The conversation is protected: nothing here calls the session.
``Terminal`` below declares the hooks it needs and is registered at ``LOCAL``,
because the user is peer zero — exactly what ``_Chat`` does, with the
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
    HookOnAsk,
    HookOnSay,
    HookPeers,
    HookSay,
    Context,
    Peers,
    Say,
    connector,
    require,
    tool,
)


@connector("eco")
@require(HookOnSay)
@require(HookSay)
class EchoConnector:
    """Answers whatever is said to everyone, and never its own answers.

    A sender does not hear its own broadcast, which is what stops this from
    answering itself forever.
    """

    say : Say

    async def on_say(self, msg: ChatMessage) -> None:
        """Replies to the message that was just said."""
        await self.say("Received: %s" % msg.text, reply_to=msg.id)


@tool("upper", "Upper-case the rest of the line")
@require(HookOnAsk)
class UpperCommand:
    """Shouts its arguments back."""

    async def on_ask(self, msg: ChatMessage) -> str:
        """Returns the question in upper case."""
        return msg.text.upper() if msg.text else "Usage: /upper <text>"


@require(HookSay)
@require(HookAsk)
@require(HookOnSay)
@require(HookOnAsk)
@require(HookContext)
@require(HookPeers)
class Terminal:
    """The presentation layer: prints what arrives, sends what is typed."""

    # Granted by the session at attach.
    say           : Say
    ask           : Ask
    context : Context
    peers  : Peers

    async def on_say(self, msg: ChatMessage) -> None:
        """Renders one broadcast on a plain terminal."""
        reply = " (replying to %s)" % msg.reply_to if msg.reply_to else ""
        print("< %s%s" % (msg.text, reply))

    async def on_ask(self, msg: ChatMessage) -> Optional[str]:
        """Shows a question put to the user; the reply is theirs to type."""
        print("? %s  — reply with  =<answer>" % msg.text)
        return None

    async def command(self, line: str) -> None:
        """Runs ``/name args``: an ask addressed to the tool of that name."""
        name, _, args = line.partition(" ")
        at = next((i for i, w in self.peers().items()
                   if i != LOCAL and getattr(w, "name", "") == name), None)
        if at is None:
            print("? unknown command: /%s — try /help" % name)
            return
        print("> /%s %s" % (name, args))
        print("< %s" % await self.ask(at, args.strip()))


async def read_lines() -> List[str]:
    """Reads stdin off the event loop, so nothing blocks while we wait."""
    return await asyncio.get_running_loop().run_in_executor(None, sys.stdin.readlines)


async def main() -> None:
    """Builds a headless chat and drives it from stdin."""
    session = ChatSession()
    view = Terminal()
    session.attach(view, at=LOCAL)
    session.attach(HelpCommand())
    session.attach(UpperCommand())
    # Registered last on purpose: hooks fire in registration order, and the
    # echo answers re-entrantly, so listening first keeps the reply below the
    # message it answers.
    session.attach(EchoConnector())
    await session.start()

    print("Type a message, /help for commands, /quit to leave.")
    for line in await read_lines():
        text = line.strip()
        if not text or text in ("/quit", "/exit"):
            break
        if text.startswith("/"):
            await view.command(text[1:].strip())
        else:
            print("> %s" % text)
            await view.say(text)
            # Nothing blocks here: the echo answers on its own queue, so give
            # the loop a moment to run it before reading the next line.
            await asyncio.sleep(0.05)

    await session.close()
    print("--- %d messages, no terminal UI ---" % len(view.context()))


if __name__ == "__main__":
    asyncio.run(main())
