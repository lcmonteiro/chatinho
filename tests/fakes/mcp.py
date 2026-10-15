"""What the MCP tests share: a remote session, a client onto it, and peers to ask."""

import asyncio
import pathlib
from typing import Any, List, Optional

import mcp_types as types
from fastmcp import Client

from chatinho import HookAnswer, HookKeep, HookLink, HookListen, HookPeers, HookSay
from chatinho import LOCAL, ChatSession, Reply
from chatinho import backend, connector, require
from chatinho.frontends.mcp import McpFrontend


async def remote(*peers: Any, backend: Any = None, commands: Any = (), **options: Any):
    """A started session served by an McpFrontend, with *peers* and *commands* in it."""
    options.setdefault("token", "t")
    front   = McpFrontend(**options)
    session = ChatSession(frontend=front, connectors=list(peers), commands=list(commands), backend=backend)
    await session.start()
    return session, front


def client(front: McpFrontend, name: str = "lab") -> Client:
    """A modern MCP client onto *front*, in-process."""
    return Client(front.server, client_info=types.Implementation(name=name, version="1"))


async def ask(c: Client, peer: str, text: str) -> dict:
    """Calls the ask tool; see :func:`call`."""
    return await call(c, "ask", peer=peer, text=text)


async def call(c: Client, tool: str, **args: Any) -> dict:
    """Calls one of the frontend's tools: its answer, or ``{status: error, text}`` for a tool error."""
    res = await c.call_tool_mcp(tool, args)
    if res.is_error:
        return {"status": "error", "text": res.content[0].text}
    return res.structured_content


@connector("weather")
@require(HookAnswer)
class Weather:
    """Answers every question it is asked, and remembers them."""

    def __init__(self, reply: Any = "sunny", delay: float = 0.0) -> None:
        self.reply = Reply(reply) if isinstance(reply, str) else reply
        self.delay = delay
        self.asked : List[Any] = []

    async def answer(self, msg):
        self.asked.append(msg)
        if self.delay:
            await asyncio.sleep(self.delay)
        return self.reply


@connector("agent")
@require(HookAnswer)
@require(HookListen)
@require(HookSay)
@require(HookPeers)
class Agent:
    """Answers questions asked to it, and replies to questions said to the room.

    With ``key``, it reads the credential ``llm`` the message carries, or None.
    """

    def __init__(self, name: str = "agent", replies: bool = True, key: bool = False,
                 delay: float = 0.0, attach: Optional[Any] = None) -> None:
        self.name    = name
        self.replies = replies
        self.key     = key
        self.delay   = delay
        self.attach  = attach
        self.heard   : List[Any] = []
        self.keys    : List[Any] = []

    async def _respond(self, msg) -> Reply:
        if self.key:
            lent = msg.credentials.get("llm")
            self.keys.append(lent.reveal() if lent is not None else None)
        if self.delay:
            await asyncio.sleep(self.delay)
        text = "%s: %s" % (self.name, msg.text)
        if self.attach is not None:
            return Reply(text + " [chart](chart.svg)", (self.attach,))
        return Reply(text)

    async def answer(self, msg):
        return await self._respond(msg)

    async def listen(self, msg):
        """Replies to a question the frontend said to the room for a client."""
        self.heard.append(msg)
        if not self.replies or not msg.is_broadcast:
            return
        if msg.frm != LOCAL:                     # only what the frontend forwarded
            return
        reply = await self._respond(msg)
        await self.say(reply.text, reply_to=msg.id, attachments=reply.attachments)


@backend("files")
@require(HookKeep)
@require(HookLink)
class Files:
    """Keeps attachments as files and links to them."""

    def __init__(self, root: pathlib.Path) -> None:
        self.root = root

    async def keep(self, msg_id, attachments):
        for item in attachments:
            path = self.root / str(msg_id) / item.name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(item.data)

    async def link(self, msg_id, name):
        path = self.root / str(msg_id) / name
        return path.as_uri() if path.exists() else None
