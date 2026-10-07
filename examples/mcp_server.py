"""A chat with no terminal, served over MCP: another session can ask it questions.

``McpFrontend`` takes the terminal's place as peer zero. Its only peer here,
``agent``, thinks with the model of whoever asked — the asking session runs the
completion, so no API key ever comes to this machine — and answers plainly when
the asker lends none.

Over stdio (what ``McpConnector(command=[...])`` starts):

    python examples/mcp_server.py

Over Streamable HTTP, with a bearer token every request must carry:

    CHATINHO_MCP_TOKEN=s3cret python examples/mcp_server.py --http 8000

and, from another chat:

    McpConnector(url="http://127.0.0.1:8000/mcp", token="s3cret", name="lab")

Needs ``pip install 'chatinho[mcp]'``.
"""

import os
import sys

from chatinho import ChatSession, HookAnswer, HookSample, SamplingUnavailable, connector, require
from chatinho.mcp import McpFrontend


@connector("agent")
@require(HookAnswer)
@require(HookSample)
class Agent:
    """Answers with the asker's model when it lends one, and plainly when it does not."""

    async def answer(self, msg) -> str:
        try:
            thought = await self.sample(
                msg.id,
                [{"role": "user", "content": msg.text}],
                system="You answer in one short sentence.",
                max_tokens=200,
            )
        except SamplingUnavailable:
            return "You asked: %s (lend me a model and I will think about it)" % msg.text
        return thought


def main() -> None:
    """Serves the session over stdio, or over HTTP with --http PORT."""
    if "--http" in sys.argv:
        port  = int(sys.argv[sys.argv.index("--http") + 1])
        front = McpFrontend(transport="http", port=port, token=os.environ["CHATINHO_MCP_TOKEN"])
    else:
        front = McpFrontend()
    ChatSession(frontend=front, connectors=[Agent()]).run()


if __name__ == "__main__":
    main()
