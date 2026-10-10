"""Putting text on the clipboard, by whatever route the terminal allows.

Textual copies with **OSC 52**, an escape sequence the terminal is free to
ignore — and several do, Termux among the ones reported here. So this tries a
clipboard *helper* as well: a small program the system already has, which
writes the clipboard directly rather than asking the terminal to.

Both routes run, because neither is sufficient alone:

- over SSH, a helper writes the **server's** clipboard, which nobody can see,
  and OSC 52 is what reaches the person at the keyboard;
- in a terminal that drops OSC 52, the helper is the only thing that works.

Nothing here imports Textual, so it is exercised without mounting anything.
"""

import logging
import shutil
import subprocess
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

#: Programs that set the clipboard, most specific first. Termux leads because
#: it is the case that sent us looking: its terminal drops OSC 52, and
#: ``termux-clipboard-set`` is the documented way in on Android.
HELPERS : Tuple[Tuple[str, ...], ...] = (
    ("termux-clipboard-set",),
    ("wl-copy",),
    ("xclip", "-selection", "clipboard"),
    ("xsel", "--clipboard", "--input"),
    ("pbcopy",),
)

#: Long enough for a helper that has to reach an Android clipboard service,
#: short enough that a wedged one is not a hung chat.
TIMEOUT : float = 5.0


def helper() -> Optional[List[str]]:
    """The first clipboard helper this system actually has.

    Returns:
        Optional[List[str]]: The command to run, or None when none is
        installed — which is the ordinary case on a plain server.
    """
    for command in HELPERS:
        if shutil.which(command[0]):
            return list(command)
    return None


def put(text: str) -> Optional[str]:
    """Writes *text* to the clipboard with a helper, if there is one.

    This is the blocking half — a helper is a subprocess, and an Android one
    can take a moment — so callers run it off the event loop.

    Args:
        text: What to put on the clipboard.

    Returns:
        Optional[str]: The name of the helper that took it, or None if there
        was none to try or it failed. A failure is logged, not raised: the
        chat has already copied by the other route, and a clipboard is never
        worth interrupting a conversation for.
    """
    command = helper()
    if command is None:
        return None
    try:
        subprocess.run(
            command,
            input   = text.encode("utf-8"),
            timeout = TIMEOUT,
            check   = True,
            stdout  = subprocess.DEVNULL,
            stderr  = subprocess.DEVNULL,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("Clipboard helper %r failed: %s", command[0], exc)
        return None
    return command[0]
