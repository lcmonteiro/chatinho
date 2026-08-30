"""A connector that an agent can start a conversation through.

The other examples show the outbound half — the user asks, the far side
answers. This one shows the inbound half: an agent asks *the user* something,
the question lands in the chat, and the user's reply is routed back to the
agent that asked, correlated by the agent's own task id.

The connector brings its own listener: a small HTTP server on a background
thread, using nothing but the standard library. Declaring ``HookAnswer`` is
what says "the far side can start a conversation": ``require`` checks the class
implements ``answer``, and the session grants it an ``inbox`` to call. The
transport machinery belongs to the connector, not to the library and not to you.

Run it:

    python examples/agent_inbox.py

then, from another terminal, play the agent:

    curl -XPOST localhost:8765/ask -d '{"task": "t1", "text": "Deploy to prod?"}'

Answer in the chat by replying to the question (type ``t1: yes``) and the
answer is posted back to the agent — here, printed by the connector.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Optional

from chatinho import (
    ChatMessage,
    ChatSession,
    HookAnswer,
    HookAsk,
    connector,
    require,
)

HOST = "127.0.0.1"
PORT = 8765


@connector("agent")
@require(HookAsk)
@require(HookAnswer)
class AgentConnector:
    """A two-way link: the user can ask the agent, and the agent can ask back.

    Inbound arrives as ``POST /ask`` with ``{"task": ..., "text": ...}``; the
    handler calls ``self.inbox``, which the session granted because this class
    declares ``HookAnswer``. Safe to call from this server thread.
    """

    def __init__(self, host: str = HOST, port: int = PORT) -> None:
        self.host = host
        self.port = port
        self._server: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    # === Lifecycle ==============================================================

    def initialize(self) -> None:
        """Starts the listener on a background thread."""
        connector = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802 — http.server's spelling
                length = int(self.headers.get("Content-Length", 0))
                payload = json.loads(self.rfile.read(length) or b"{}")
                connector.inbox(payload.get("text", ""), payload.get("task"))
                self.send_response(202)
                self.end_headers()

            def log_message(self, fmt: str, *args) -> None:
                """Keeps the server quiet: the chat owns the terminal."""

        self._server = ThreadingHTTPServer((self.host, self.port), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def shutdown(self) -> None:
        """Stops the listener. Without this the thread outlives the chat."""
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None

    # === Outbound ===============================================================

    def ask(self, message: str, **kwargs) -> Any:
        """The user asks the agent. Stubbed here — the demo is about inbound."""
        return "the agent would answer: %s" % message

    def answer(self, correlation_id: Optional[str], text: str) -> None:
        """The user's reply, routed back to the task that asked for it.

        A real connector would POST this to the agent's callback URL.
        """
        print(f"\n  → answered task {correlation_id!r}: {text}\n")


def main() -> None:
    """Runs a headless chat with an agent-facing inbox."""
    agent = AgentConnector()
    session = ChatSession(connectors=[agent])

    def show(msg: ChatMessage) -> None:
        if msg.is_sent_by_me:
            return
        tag = f" [{msg.origin}/{msg.correlation_id}]" if msg.origin else ""
        print(f"< {msg.text}{tag}")

    session.on_message_added = show

    print(f"Listening on http://{HOST}:{PORT}/ask — the agent asks, you answer.")
    print('  curl -XPOST %s:%d/ask -d \'{"task": "t1", "text": "Deploy?"}\'' % (HOST, PORT))
    print("Reply with  <task-id>: <answer>   e.g.  t1: yes.   /quit to leave.\n")

    try:
        while True:
            try:
                line = input("you> ").strip()
            except EOFError:
                break
            if not line or line == "/quit":
                break
            task, _, answer = line.partition(":")
            question = next(
                (m for m in reversed(session.messages) if m.correlation_id == task.strip()),
                None,
            )
            if question is None:
                print(f"  no open question for task {task.strip()!r}")
                continue
            session.send_message(answer.strip(), reply_to=question.id)
    finally:
        session.close()
        print("--- listener stopped ---")


if __name__ == "__main__":
    main()
