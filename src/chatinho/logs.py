"""
The log file a chat writes: ``chatinho.<date>.log`` in the system's temporary directory.

:meth:`ChatSession.run` opens it, and nothing else does: importing chatinho, or
driving a session with ``start`` and ``close``, configures no logging at all.
Once open, every record of the ``chatinho`` loggers, from DEBUG up, is written
to the file by a thread of its own, and the program's own logging still gets
exactly the records it got before.
"""

import logging
from datetime import date
from pathlib import Path
from typing import Optional

#: One record per line: the time, the level, the process (what tells two chats sharing a day's file
#: apart) and the logger.
LOG_FORMAT : str = "%(asctime)s %(levelname)s [%(process)d] %(name)s: %(message)s"

logger = logging.getLogger(__name__)


def log_file(day: Optional[date] = None) -> Path:
    """
    Where the log of *day* goes: ``<tempdir>/chatinho.<YYYY-MM-DD>.log``.

    Args:
        day: The day; today when None.

    Returns:
        Path: The file's path, in :func:`tempfile.gettempdir`.
    """
    raise NotImplementedError


def open_log() -> Optional[Path]:
    """
    Sends every ``chatinho`` record to today's log file, once per process.

    A second call returns the same path and adds nothing. When the file cannot
    be opened, one line on stderr says so and the chat goes on without it.

    Returns:
        Optional[Path]: The file being written, or None when it cannot be.
    """
    raise NotImplementedError


def close_log() -> None:
    """Stops writing the file, and puts the ``chatinho`` logger back as it was."""
    raise NotImplementedError
