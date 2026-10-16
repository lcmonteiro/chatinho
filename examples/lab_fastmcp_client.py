"""A plain FastMCP client asking the lab — no chatinho needed on this side.

It lists the lab's peers, then asks one question, lending ``OPENAI_API_KEY`` in
the request's ``_meta`` the way an ``McpConnector`` does.

    CHATINHO_MCP_TOKEN=s3cret python examples/lab_server.py 8000
    CHATINHO_MCP_TOKEN=s3cret OPENAI_API_KEY=sk-... \\
        python examples/lab_fastmcp_client.py http://127.0.0.1:8000/mcp "what is MCP?"

Needs ``pip install fastmcp``.
"""

import asyncio
import os
import sys

from fastmcp import Client


async def talk(client: Client, text: str, key: str) -> None:
    """Prints who is there, then the lab's answer to *text*."""
    async with client:
        for peer in (await client.call_tool("peers")).data:
            print("peer:", peer.name, "(answers)" if peer.answers else "")
        result = await client.call_tool("ask", {"peer": "lab", "text": text},
                                        meta={"chatinho/credentials": {"llm": key}})
        answer = result.structured_content or {}
        print(answer.get("status"), "-", answer.get("text"))


def main() -> None:
    """Asks the lab at the URL given."""
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise SystemExit("set OPENAI_API_KEY (any OpenAI-compatible key); see examples/README.md")
    url  = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/mcp"
    text = sys.argv[2] if len(sys.argv) > 2 else "In one sentence, what is MCP?"
    asyncio.run(talk(Client(url, auth=os.environ["CHATINHO_MCP_TOKEN"]), text, key))


if __name__ == "__main__":
    main()
