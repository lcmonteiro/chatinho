"""
The log file a chat writes: ``chatinho.<date>.log`` in the system's temporary directory.

:meth:`ChatSession.run` opens it, and nothing else does: importing chatinho, or
driving a session with ``start`` and ``close``, configures no logging at all.
Once open, every record of the ``chatinho`` loggers, from DEBUG up, is written
to the file by a thread of its own, so a slow disk never holds up the chat.

The program's own logging still gets exactly the records it got before. For
the file to see DEBUG, the ``chatinho`` logger's level has to be DEBUG, and
left propagating that would hand every DEBUG record to the program's root
handlers, which usually have no level of their own (``basicConfig`` sets it on
the logger). So the ``chatinho`` logger stops propagating, and a handler of
its own passes a record on to the root logger only when it reaches the level
that would have let it through before: the level the program gave the
``chatinho`` logger, or else the root logger's, read at each record.
"""

import atexit
import logging
import logging.handlers
import queue
import sys
import tempfile
from datetime import date
from pathlib import Path
from typing import Any, Optional

#: One record per line: the time, the level, the process (what tells two chats sharing a day's file
#: apart) and the logger.
LOG_FORMAT : str = "%(asctime)s %(levelname)s [%(process)d] %(name)s: %(message)s"

#: The logger every record of chatinho goes through.
ROOT : str = "chatinho"


class _Forward(logging.Handler):
    """Passes a record on to the root logger when it reaches the level the program would have let through."""

    def __init__(self, level: Optional[int]) -> None:
        super().__init__()
        #: The level the program gave the ``chatinho`` logger; None: the root logger's, read each time.
        self.threshold = level

    def emit(self, record: logging.LogRecord) -> None:
        threshold = self.threshold if self.threshold is not None else logging.getLogger().getEffectiveLevel()
        if record.levelno >= threshold:
            logging.getLogger().handle(record)


class _Open:
    """What an open log is made of, to be undone by :func:`close_log`."""

    def __init__(self, path: Path, listener: Any, handlers: Any, level: int, propagate: bool) -> None:
        self.path      = path
        self.listener  = listener
        self.handlers  = handlers
        self.level     = level
        self.propagate = propagate


_open   : Optional[_Open] = None
#: The file could not be opened once already: say nothing more.
_failed : bool = False


def log_file(day: Optional[date] = None) -> Path:
    """
    Where the log of *day* goes: ``<tempdir>/chatinho.<YYYY-MM-DD>.log``.

    Args:
        day: The day; today when None.

    Returns:
        Path: The file's path, in :func:`tempfile.gettempdir`.
    """
    return Path(tempfile.gettempdir()) / ("chatinho.%s.log" % (day or date.today()).isoformat())


# @req REQ-CORE-034
def open_log() -> Optional[Path]:
    """
    Sends every ``chatinho`` record to today's log file, once per process.

    A second call returns the same path and adds nothing. When the file cannot
    be opened, one line on stderr says so and the chat goes on without it.

    Returns:
        Optional[Path]: The file being written, or None when it cannot be.
    """
    global _open, _failed
    if _open is not None:
        return _open.path
    if _failed:
        return None
    path = log_file()
    try:
        writer = logging.FileHandler(path, mode="a", encoding="utf-8")
    except OSError as exc:
        _failed = True
        print("chatinho: cannot write the log file %s: %s" % (path, exc), file=sys.stderr)
        return None
    writer.setFormatter(logging.Formatter(LOG_FORMAT))
    records  : "queue.SimpleQueue[logging.LogRecord]" = queue.SimpleQueue()
    listener = logging.handlers.QueueListener(records, writer)
    listener.start()
    chatinho = logging.getLogger(ROOT)
    handlers = (logging.handlers.QueueHandler(records), _Forward(chatinho.level or None))
    _open    = _Open(path, listener, handlers, chatinho.level, chatinho.propagate)
    for handler in handlers:
        chatinho.addHandler(handler)
    chatinho.setLevel(logging.DEBUG)
    chatinho.propagate = False
    return path


def close_log() -> None:
    """Stops writing the file, and puts the ``chatinho`` logger back as it was."""
    global _open, _failed
    _failed = False
    if _open is None:
        return
    done, _open = _open, None
    chatinho = logging.getLogger(ROOT)
    for handler in done.handlers:
        chatinho.removeHandler(handler)
    chatinho.setLevel(done.level)
    chatinho.propagate = done.propagate
    done.listener.stop()                                      # writes what is still queued
    for handler in done.listener.handlers:
        handler.close()


atexit.register(close_log)
