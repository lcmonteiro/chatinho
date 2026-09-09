"""A connector that an agent can start a conversation through.

The other examples show the outbound half — the user asks, the far side
answers. This one shows the inbound half: an agent asks *the user* something
through ``ask(LOCAL, ...)``, the question lands in the chat, and the user's
reply resolves the very ``await`` the agent is sitting on. There is no inbox,
no correlation id and no routing code: an ask is addressed and owed, and the
session matches the reply to it.

The connector brings its own listener: a small HTTP server on a background
thread, using nothing but the standard library. Because that thread is not the
event loop, it hands its work over with ``run_coroutine_threadsafe``.

Run it:

    python examples/agent_inbox.py

then, from another terminal, play the agent:

    curl -XPOST localhost:8765/ask -d '{"text": "Deploy to prod?"}'

Answer in the chat by typing the answer, and it is posted back to the agent —
here, printed by the connector.
"""

import asyncio
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import List, Optional

from chatinho import (
    LOCAL,
    Ask,
    ChatMessage,
    ChatSession,
    HookAsk,
    HookContext,
    HookAnswer,
    HookListen,
    HookSay,
    Context,
    Say,
    connector,
    require,
)

HOST = "127.0.0.1"
PORT = 8765


@connector("agent")
@require(HookAsk)
class AgentConnector:
    """A one-way link inwards: the agent asks, the user answers.

    Inbound arrives as ``POST /ask`` with ``{"text": ...}``; the handler runs
    on the server's own thread, so it schedules the ask onto the loop rather
    than touching it directly.
    """

    ask : Ask

    def __init__(self, host: str = HOST, port: int = PORT) -> None:
        self.host = host
        self.port = port
        self._server : Optional[ThreadingHTTPServer] = None
        self._thread : Optional[threading.Thread] = None
        self._loop   : Optional[asyncio.AbstractEventLoop] = None

    async def serve(self) -> None:
        """Starts the listener and keeps it up until the chat ends.

        ``serve`` means *runs until it is finished*, and this one never
        finishes on its own: it waits, and the session cancels it when the
        terminal's own ``serve`` returns. Then ``shutdown`` stops the thread.

        It cannot be ``initialize``: that is called at ``attach``, where there
        is no running loop to hand the handler thread.
        """
        self._loop = asyncio.get_running_loop()
        agent = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802 — http.server's spelling
                length  = int(self.headers.get("Content-Length", 0))
                payload = json.loads(self.rfile.read(length) or b"{}")
                agent.put(payload.get("text", ""))
                self.send_response(202)
                self.end_headers()

            def log_message(self, fmt: str, *args) -> None:
                """Keeps the server quiet: the chat owns the terminal."""

        self._server = ThreadingHTTPServer((self.host, self.port), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

        await asyncio.Event().wait()        # until the session cancels us

    def put(self, text: str) -> None:
        """Asks the user, from the server thread, and prints the answer.

        The ask is a coroutine and this is not the loop, so it is handed over
        with ``run_coroutine_threadsafe`` and answered whenever the user gets
        round to it.
        """
        if self._loop is None:
            return

        async def asked() -> None:
            answer = await self.ask(LOCAL, text)
            print("\n  → the user answered: %s\n" % answer)

        asyncio.run_coroutine_threadsafe(asked(), self._loop)

    def shutdown(self) -> None:
        """Stops the listener. Without this the thread outlives the chat."""
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None


@connector("terminal", id=LOCAL)
@require(HookSay)
@require(HookListen)
@require(HookAnswer)
@require(HookContext)
class Terminal:
    """The user: shows the agent's questions and lets them be answered."""

    say           : Say
    context : Context

    async def listen(self, msg: ChatMessage) -> None:
        """Renders a broadcast."""
        print("< %s" % msg.text)

    async def answer(self, msg: ChatMessage) -> Optional[str]:
        """Shows the question; the answer is whatever the user types next."""
        print("\n< %s   [%s asks]" % (msg.text, msg.frm))
        return None

    async def serve(self) -> None:
        """Answers from stdin until it ends, and that ends the chat.

        The inbox keeps listening on its own thread meanwhile; when this
        returns, the session closes and the connector's ``shutdown`` stops it.
        """
        print("Listening on http://%s:%d/ask — the agent asks, you answer." % (HOST, PORT))
        print('  curl -XPOST %s:%d/ask -d \'{"text": "Deploy?"}\'' % (HOST, PORT))
        print("Type your answer to whatever it asks.   /quit to leave.\n")
        for line in await read_lines():
            text = line.strip()
            if not text or text == "/quit":
                break
            unanswered = next(
                (m for m in reversed(self.context())
                 if m.to == LOCAL and not any(r.reply_to == m.id for r in self.context())),
                None,
            )
            await self.say(text, reply_to=unanswered.id if unanswered else None)
            await asyncio.sleep(0.05)
        print("--- listener stopped ---")


async def read_lines() -> List[str]:
    """Reads stdin off the event loop, so the listener keeps serving."""
    return await asyncio.get_running_loop().run_in_executor(None, sys.stdin.readlines)


def main() -> None:
    """Runs a headless chat with an agent-facing inbox."""
    ChatSession(connectors=[Terminal(), AgentConnector()]).run()


if __name__ == "__main__":
    main()
