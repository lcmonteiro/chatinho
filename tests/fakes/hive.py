"""
A real hive for the tests: a database with chats and an admin key, served on a free port.

Not a double: it is ``chatinho.hive`` itself, made with its own commands and
served by uvicorn on a thread, so ``HiveBackend`` talks HTTP to it as it would
to any hive. :func:`down_url` is an address where nothing listens.
"""

import contextlib
import io
import socket
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, Iterator, List, Optional

from chatinho import LOCAL, ChatMessage, MessageID, ReplyStatus


@dataclass
class Hive:
    """A hive's database and its keys, by chat name."""

    db    : str
    admin : str
    keys  : Dict[str, str] = field(default_factory=dict)


def command(*argv: str) -> str:
    """Runs ``chatinho-hive`` with *argv*; returns what it printed. Fails the test on a non-zero exit."""
    from chatinho.hive.cli import main

    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        status = main(list(argv))
    assert status == 0, out.getvalue()
    return out.getvalue()


def key_in(printed: str) -> str:
    """The key a ``chat add`` or ``admin add`` printed."""
    return next(word for word in printed.split() if word.startswith("hive_"))


def make_hive(tmp_path: Any, *chats: str) -> Hive:
    """A new hive database under *tmp_path*, with *chats* and one admin key."""
    db   = "sqlite:///%s" % (tmp_path / "hive.db")
    hive = Hive(db=db, admin=key_in(command("admin", "add", "--db", db)))
    for name in chats:
        hive.keys[name] = key_in(command("chat", "add", name, "--db", db))
    return hive


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def down_url() -> str:
    """An address where no hive listens."""
    return "http://127.0.0.1:%d" % free_port()


class Served:
    """A hive served by uvicorn on a thread, on *port*; stop it with :meth:`stop`."""

    def __init__(self, db: str, port: Optional[int] = None) -> None:
        import uvicorn

        from chatinho.hive import create_app

        self.port   = port or free_port()
        self.url    = "http://127.0.0.1:%d" % self.port
        config      = uvicorn.Config(create_app(db), host="127.0.0.1", port=self.port, log_level="warning")
        self.server = uvicorn.Server(config)
        self.thread = threading.Thread(target=self.server.run, daemon=True)
        self.thread.start()
        deadline = time.monotonic() + 10
        while not self.server.started:
            if time.monotonic() > deadline:
                raise RuntimeError("the hive did not start")
            time.sleep(0.02)

    def stop(self) -> None:
        self.server.should_exit = True
        self.thread.join(timeout=10)


@contextlib.contextmanager
def served(db: str, port: Optional[int] = None) -> Iterator[Served]:
    """Serves the hive at *db* for the length of the block."""
    hive = Served(db, port)
    try:
        yield hive
    finally:
        hive.stop()


_T0 = datetime(2026, 1, 1, 12, 0, 0)


def message(n: int, text: Optional[str] = None, **fields: Any) -> ChatMessage:
    """Message number *n*, *n* minutes after a fixed time, so ordering is by *n*."""
    return ChatMessage(id=fields.pop("id", MessageID.new()), text=text or "message %d" % n,
                       frm=fields.pop("frm", LOCAL), timestamp=_T0 + timedelta(minutes=n),
                       status=fields.pop("status", ReplyStatus.ANSWERED), **fields)


def wire_messages(*messages: ChatMessage, name: str = "me") -> List[Dict[str, Any]]:
    """*messages* as a chat posts them."""
    from chatinho.support.parts.hive import message_to_wire

    return [message_to_wire(m, name) for m in messages]
