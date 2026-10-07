"""A chat with no terminal, served over MCP: another session can ask it questions.

``McpFrontend`` takes the terminal's place as peer zero, over Streamable HTTP
with a bearer token every request must carry. Its only peer here, ``agent``,
uses an LLM key only when the asker lends one for that question — declared as
``llm``, delegated out of band, and gone once the answer is sent — and answers
plainly when nobody lends one.

    CHATINHO_MCP_TOKEN=s3cret python examples/mcp_server.py 8000

and, from another chat:

    McpConnector(url="http://127.0.0.1:8000/mcp", token="s3cret", name="lab",
                 delegate={"llm": my_sub_key})

Needs ``pip install 'chatinho[mcp]'``.
"""

import os
import sys

from chatinho import ChatSession, CredentialUnavailable, HookAnswer, HookCredential, connector, require
from chatinho.frontends.mcp import McpFrontend


@connector("agent")
@require(HookAnswer)
@require(HookCredential)
class Agent:
    """Answers with the asker's key when it lends one, and plainly when it does not."""

    async def answer(self, msg) -> str:
        try:
            key = await self.credential(msg.id, "llm")
        except CredentialUnavailable:
            return "You asked: %s (lend me a key and I will think about it)" % msg.text
        # A real agent builds its model with *key* here, for this answer only.
        return "Thinking about %r with the key you lent (%d characters)" % (msg.text, len(key))


def main() -> None:
    """Serves the session over HTTP on the port given, 8000 by default."""
    port  = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    front = McpFrontend(token=os.environ["CHATINHO_MCP_TOKEN"], port=port,
                        credentials={"llm": "OpenAI-compatible API key"})
    ChatSession(frontend=front, connectors=[Agent()]).run()


if __name__ == "__main__":
    main()
