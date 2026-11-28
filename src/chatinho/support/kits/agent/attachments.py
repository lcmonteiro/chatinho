"""
The files a question came with, as the agent reads them: inlined in the question, and ``read_attachment``.

A message never carries its files: its text links each by name and ``locate``
says where the backend keeps it. Before a run, the peer reads back every file
the question links; one that is text is put in the question the model is sent,
whole or up to :data:`ATTACHMENT_SHOWN` characters, and one that is not is
named with its type and size. ``read_attachment`` reads any line window of a
file the question, or a message the agent remembers, links.
"""

import asyncio
import mimetypes
from dataclasses import dataclass
from typing import Any, List, Optional

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import StructuredTool

from ....message import ChatMessage
from ...parts.attachments import linked_names, read_link
from ...parts.memory import earlier

#: How many characters of a text file the question shows the model; ``read_attachment`` reads the rest.
ATTACHMENT_SHOWN : int = 20000

#: How many lines ``read_attachment`` reads when it is not told.
READ_LINES : int = 400

#: Where a run's configuration carries the question, for ``read_attachment``.
QUESTION_KEY = "chatinho_question"


@dataclass(frozen=True)
class Attached:
    """
    One file a message links, read back.

    Attributes:
        name: The name the message links it by.
        media_type: What it most likely holds, from its name.
        data: Its bytes.
    """

    name       : str
    media_type : str
    data       : bytes

    @property
    def text(self) -> Optional[str]:
        """Its content as text, or None when it is not UTF-8 text."""
        try:
            decoded = self.data.decode("utf-8")
        except UnicodeDecodeError:
            return None
        return None if "\x00" in decoded else decoded


# @req REQ-AGENT-014
async def read_attached(peer: Any, msg: ChatMessage, only: Optional[str] = None) -> List[Attached]:
    """
    The files *msg* links that the backend gives back, in the order linked; only *only* when given.

    Nothing without a ``locate`` grant; a name the backend has nothing for is
    left out. The reads go to a thread.
    """
    locate = getattr(peer, "locate", None)
    if locate is None:
        return []
    found : List[Attached] = []
    for name in linked_names(msg.text):
        if only is not None and name != only:
            continue
        data = await asyncio.to_thread(read_link, await locate(msg.id, name))
        if data is not None:
            found.append(Attached(name, mimetypes.guess_type(name)[0] or "application/octet-stream", data))
    return found


# @req REQ-AGENT-014
def inlined(files: List[Attached]) -> str:
    """What the question adds for *files*: each text file's content, and what any other one is."""
    parts : List[str] = []
    for f in files:
        text = f.text
        if text is None:
            parts.append('<attachment name="%s" type="%s" bytes="%d">not text; it cannot be shown'
                         '</attachment>' % (f.name, f.media_type, len(f.data)))
            continue
        lines = _lines(text)
        kept, size = 0, 0
        while kept < len(lines) and size + len(lines[kept]) <= ATTACHMENT_SHOWN:
            size += len(lines[kept])
            kept += 1
        body = "".join(lines[:kept])
        if kept < len(lines):
            body += ("[cut after line %d of %d; read on with read_attachment(name=%r, start=%d)]\n"
                     % (kept, len(lines), f.name, kept + 1))
        parts.append('<attachment name="%s" type="%s">\n%s</attachment>'
                     % (f.name, f.media_type, body if body.endswith("\n") else body + "\n"))
    return "\n\n".join(parts)


# @req REQ-AGENT-014
def read_attachment_tool(peer: Any) -> StructuredTool:
    """``read_attachment``: a line window of a file the question, or a message remembered, links."""

    async def read_attachment(name: str, start: int = 1, count: int = READ_LINES,
                              *, config: RunnableConfig) -> str:
        question = (config.get("configurable") or {}).get(QUESTION_KEY)
        if not isinstance(question, ChatMessage):
            return "no question is being answered"
        candidates = [question] + list(reversed(earlier(peer.context, peer.memory, question)))
        for m in candidates:
            if name not in linked_names(m.text):
                continue
            found = await read_attached(peer, m, only=name)
            if found:
                return _window(found[0], start, count)
        return "no attached file is called %r" % name

    return StructuredTool.from_function(
        coroutine   = read_attachment,
        name        = "read_attachment",
        description = ("Read lines of a file attached to the question, or to an earlier message, by "
                       "the name it is linked by; start is the first line, from 1."))


def _window(f: Attached, start: int, count: int) -> str:
    text = f.text
    if text is None:
        return "%s is %s, %d bytes, and not text" % (f.name, f.media_type, len(f.data))
    lines = _lines(text)
    first = max(start, 1) - 1
    taken : List[str] = []
    size  = 0
    for line in lines[first:first + max(count, 1)]:
        if taken and size + len(line) > ATTACHMENT_SHOWN:
            break
        taken.append(line)
        size += len(line)
    if not taken:
        return "[%s has %d lines]" % (f.name, len(lines))
    last = first + len(taken)
    more = ", more follow" if last < len(lines) else ""
    return "[%s, lines %d-%d of %d%s]\n%s" % (f.name, first + 1, last, len(lines), more, "".join(taken))


def _lines(text: str) -> List[str]:
    """*text* as lines, each cut to what the model is shown at most, so one long line never hides the rest."""
    cut = ATTACHMENT_SHOWN - 20
    return [line if len(line) <= ATTACHMENT_SHOWN else line[:cut] + " [line cut]\n"
            for line in text.splitlines(keepends=True)]
