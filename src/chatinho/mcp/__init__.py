"""Sessions reaching each other over MCP — needs ``pip install 'chatinho[mcp]'``.

:class:`McpFrontend` serves a headless session over the modern MCP protocol,
in place of a terminal; :class:`McpConnector` is the peer that puts questions
to such a session from another chat.
"""

from .connector import McpConnector
from .frontend import McpFrontend

__all__ = ["McpConnector", "McpFrontend"]
