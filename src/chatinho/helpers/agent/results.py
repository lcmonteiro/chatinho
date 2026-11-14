"""
What a run of the agent gives back, as the chat reads it: the answer's text and the files it made.

Also how a workspace operation's result reads to a model, and a diff as an
attachment.
"""

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage

from ...message import Attachment
from ...workspaces import Lines, Matches

#: What a tool or file name may hold, for the OpenAI-compatible APIs.
UNSAFE = re.compile(r"[^A-Za-z0-9_-]")

#: How much of a diff a ``ws_diff`` tool shows the model; the attachment holds all of it.
DIFF_SHOWN : int = 20000

#: How a link reminder starts; what follows names the missing links.
REMINDER = "Your answer does not link every file you made."


def text(messages: List[BaseMessage], structured: Any) -> str:
    """The run's answer: *structured* as JSON when there is one, else the last AI message's text."""
    if structured is not None:
        dump = getattr(structured, "model_dump_json", None)
        return dump() if callable(dump) else json.dumps(structured, default=str)
    last = next((m for m in reversed(messages) if isinstance(m, AIMessage)), None)
    if last is None:
        return ""
    if isinstance(last.content, str):
        return last.content
    return "".join(block if isinstance(block, str) else str(block.get("text", ""))
                   for block in last.content
                   if isinstance(block, str) or block.get("type") == "text")


def files(messages: List[BaseMessage]) -> List[Attachment]:
    """The files the tools in *messages* made, the last of each name, in the order first made."""
    found : Dict[str, Attachment] = {}
    for m in messages:
        made = attachment(m.artifact) if isinstance(m, ToolMessage) else None
        if made is not None:
            found[made.name] = made
    return list(found.values())


def attachment(artifact: Any) -> Optional[Attachment]:
    """*artifact* as an Attachment, when it is one or looks like one."""
    if isinstance(artifact, Attachment):
        return artifact
    name, media_type = getattr(artifact, "name", None), getattr(artifact, "media_type", None)
    data = getattr(artifact, "data", None)
    if not (isinstance(name, str) and isinstance(media_type, str) and isinstance(data, (str, bytes))):
        return None
    return Attachment(name=name, media_type=media_type,
                      data=data.encode("utf-8") if isinstance(data, str) else data)


def shown(result: Any) -> str:
    """What a workspace operation returned, as the text a model reads."""
    if result is None:
        return "done"
    if isinstance(result, Lines):
        count = result.text.count("\n") + (0 if result.text.endswith("\n") or not result.text else 1)
        span  = "lines %d-%d" % (result.start, result.start + count - 1) if count else "no lines"
        return "[%s%s]\n%s" % (span, ", more follow" if result.more else "", result.text)
    if isinstance(result, Matches):
        if not result.matches:
            return "no matches"
        found = ["%s:%d%s:\n%s" % (m.path, m.start, "" if m.end == m.start else "-%d" % m.end,
                                    m.text.rstrip("\n")) for m in result.matches]
        return "\n".join(found) + ("\n[more matches were cut]" if result.truncated else "")
    if isinstance(result, (list, tuple)):
        return "\n".join(str(item) for item in result) or "(none)"
    return str(result)


def diffed(diff: str, whose: str) -> Tuple[str, Optional[Attachment]]:
    """A diff as the model reads it, and as the attachment its answer links."""
    if not diff:
        return "%s's workspace has no changes" % whose, None
    name = "%s.diff" % UNSAFE.sub("_", whose)
    cut  = diff if len(diff) <= DIFF_SHOWN else diff[:DIFF_SHOWN] + "\n[the rest is in the attachment]"
    return ("Attached as %s; link it as [%s's diff](%s).\n%s" % (name, whose, name, cut),
            Attachment(name, "text/x-diff", diff.encode("utf-8")))
