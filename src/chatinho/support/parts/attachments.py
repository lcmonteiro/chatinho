"""
What reads a message's attachments back: which names its text links, and the bytes behind a link.

A message never carries its attachments: its Markdown text links each by name
— ``[chart](chart.svg)`` — and ``locate`` asks the backend where that name can
be opened. ``McpFrontend`` reads a reply's files back this way, and
``AgentPeer`` its question's. Standard library only.
"""

import os
import re
from typing import List, Optional
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

_LINK = re.compile(r"\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")


# @req REQ-AGENT-014
def linked_names(text: str) -> List[str]:
    """
    The relative link targets in a Markdown *text*, in order, each once.

    In chatinho a message links its attachments by name — ``[chart](chart.svg)``
    — and that is the only list of them there is. Absolute URLs, paths and
    anchors are not attachments.
    """
    names: List[str] = []
    for target in _LINK.findall(text or ""):
        if ":" in target or target.startswith(("/", "#")):
            continue
        name = unquote(target)
        if name not in names:
            names.append(name)
    return names


# @req REQ-AGENT-014
def read_link(link: Optional[str]) -> Optional[bytes]:
    """
    The bytes behind what ``locate`` answered, or None for anything else or nothing there.

    A backend answers with a ``file://`` link (``DatabaseBackend``) or with a
    local path (``HiveBackend``); both are read. Any other link — ``https`` —
    is not a file here. A blocking read: call it in a thread.
    """
    if not link:
        return None
    parsed = urlparse(link)
    if parsed.scheme == "file":
        path = url2pathname(parsed.path)
    elif os.path.isabs(link):
        path = link
    else:
        return None
    try:
        with open(path, "rb") as handle:
            return handle.read()
    except OSError:
        return None
