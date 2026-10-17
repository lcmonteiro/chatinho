"""
Let a script ask you a question in the chat and wait for your answer.

The inbox is a connector with its own HTTP listener (the standard library's
``http.server``, on a background thread). ``POST /ask`` puts the question to you
in the terminal, and the HTTP request waits until you reply to it — so a deploy
script, a cron job or an agent can block on a human decision::

    answer=$(curl -s -d '{"text": "Deploy to prod?"}' 127.0.0.1:8765/ask)
    # {"answer": "yes"}

Reply by tapping the question (or selecting it) and typing. With no reply within
``CHATINHO_INBOX_TIMEOUT`` seconds (300 by default) the request gets a 504.

Run it::

    python examples/inbox.py

No model and no key: the person at the terminal is the one who answers.
Needs ``pip install 'chatinho[all]'``.
"""

import asyncio
import concurrent.futures
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional

from chatinho import LOCAL, Ask, HelpCommand, HookAsk, build_chat_session, connector, require

HOST = "127.0.0.1"
PORT = 8765


@connector("inbox")
@require(HookAsk)
class InboxConnector:
    """
    Turns ``POST /ask`` into a question for the user, and answers with their reply.

    The handler runs on the server's thread, not the event loop, so it hands
    the ask over with ``run_coroutine_threadsafe`` and blocks only its own
    thread on the result.
    """

    ask : Ask

    def __init__(self, host: str = HOST, port: int = PORT, timeout: Optional[float] = None) -> None:
        self.host    = host
        self.port    = port
        if timeout is None:
            timeout = float(os.environ.get("CHATINHO_INBOX_TIMEOUT", 300))
        self.timeout = timeout
        self._server : Optional[ThreadingHTTPServer] = None
        self._thread : Optional[threading.Thread] = None
        self._loop   : Optional[asyncio.AbstractEventLoop] = None

    async def serve(self) -> None:
        """Listens until the session cancels it; ``shutdown`` then stops the thread."""
        self._loop = asyncio.get_running_loop()
        inbox = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802 — http.server's spelling
                if self.path != "/ask":
                    return self._send(404, {"error": "POST /ask"})
                try:
                    length = int(self.headers.get("Content-Length", 0))
                    text   = json.loads(self.rfile.read(length) or b"{}")["text"]
                except (ValueError, KeyError, TypeError):
                    return self._send(400, {"error": 'send {"text": "..."}'})
                status, body = inbox.put(str(text))
                self._send(status, body)

            def _send(self, status: int, body: dict) -> None:
                data = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, fmt: str, *args) -> None:
                """Keeps the server quiet: the chat owns the terminal."""

        self._server = ThreadingHTTPServer((self.host, self.port), Handler)
        self.port    = self._server.server_address[1]      # the real one, when given 0
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        await asyncio.Event().wait()

    def put(self, text: str) -> tuple:
        """Asks the user *text* from the server thread; the HTTP status and body."""
        if self._loop is None:
            return 503, {"error": "not started"}
        future = asyncio.run_coroutine_threadsafe(self.ask(LOCAL, text), self._loop)
        try:
            return 200, {"answer": future.result(self.timeout).text}
        except concurrent.futures.TimeoutError:
            future.cancel()
            return 504, {"error": "no answer within %g s" % self.timeout}

    def shutdown(self) -> None:
        """Stops the listener. Without this the thread outlives the chat."""
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None


def parts() -> dict:
    """The inbox and /help."""
    return dict(connectors=[InboxConnector()], commands=[HelpCommand()], backend=None)


def main() -> None:
    """Opens the chat in the terminal, with the inbox listening."""
    welcome = ("Listening on http://%s:%d/ask. Questions posted there appear here; "
               "select one and type to answer." % (HOST, PORT))
    build_chat_session(**parts(), title="Inbox", welcome_message=welcome, name="me").run()


if __name__ == "__main__":
    main()
