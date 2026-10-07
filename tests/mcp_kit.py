"""What the MCP tests share: a remote session, a client onto it, and peers to ask."""

import asyncio
import pathlib
from typing import Any, List, Optional

import mcp_types as types
from mcp import Client

from chatinho import (
    LOCAL,
    ChatSession,
    HookAnswer,
    HookCredential,
    HookKeep,
    HookLink,
    HookListen,
    HookPeers,
    HookSay,
    Reply,
    backend,
    connector,
    require,
)
from chatinho.frontends.mcp import McpFrontend


async def remote(*peers: Any, backend: Any = None, **options: Any):
    """A started session served by an McpFrontend, with *peers* in it."""
    options.setdefault("token", "t")
    front   = McpFrontend(**options)
    session = ChatSession(frontend=front, connectors=list(peers), backend=backend)
    await session.start()
    return session, front


def client(front: McpFrontend, name: str = "lab") -> Client:
    """A modern MCP client onto *front*, in-process."""
    return Client(front.server, mode="auto", client_info=types.Implementation(name=name, version="1"))


async def say(c: Client, text: str, **args: Any) -> dict:
    """Calls the say tool and returns its structured result."""
    res = await c.call_tool("say", {"text": text, **args})
    return res.structured_content


@connector("weather")
@require(HookAnswer)
class Weather:
    """Answers every question it is asked, and remembers them."""

    def __init__(self, reply: Any = "sunny", delay: float = 0.0) -> None:
        self.reply = reply
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
@require(HookCredential)
@require(HookPeers)
class Agent:
    """Answers questions asked to it, and replies to questions said to the room.

    With ``key``, it reads the lent credential ``llm`` first.
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
            try:
                self.keys.append(await self.credential(msg.id, "llm"))
            except Exception as exc:
                self.keys.append(type(exc).__name__)
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
