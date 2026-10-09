"""A plain FastMCP client talking to examples/mcp_server.py — no chatinho needed.

Start the server, then run this with the same token:

    CHATINHO_MCP_TOKEN=s3cret python examples/mcp_server.py 8000
    CHATINHO_MCP_TOKEN=s3cret python examples/mcp_client.py http://localhost:8000/mcp

Needs ``pip install fastmcp``.
"""

import asyncio
import os
import sys

from fastmcp import Client

URL    = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000/mcp"
client = Client(URL, auth=os.environ["CHATINHO_MCP_TOKEN"])


async def main(text: str) -> None:
    async with client:
        for peer in (await client.call_tool("peers")).data:
            print("peer:", peer.name, "(answers)" if peer.answers else "")

        result = await client.call_tool("ask", {"peer": "agent", "text": text})
        print(result.structured_content["status"], "-", result.structured_content["text"])

        result = await client.call_tool("ask", {"peer": "agent", "text": text},
                                        meta={"chatinho/credentials": {"llm": "sk-a-sub-key"}})
        print(result.structured_content["text"])


if __name__ == "__main__":
    asyncio.run(main("what is chatinho?"))
