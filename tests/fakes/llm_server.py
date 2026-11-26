"""
A real OpenAI-compatible server on a free local port, for what a stubbed client cannot show.

:func:`serve_chat` answers ``POST /v1/chat/completions`` over plain HTTP/1.1 and
records the bearer key of every request, so a test sees the key a model was
really called with — through ``ChatOpenAI``, the OpenAI client and httpx, none
of them replaced.
"""

import asyncio
import contextlib
import json
from typing import Any, AsyncIterator, Callable, Dict, List, Optional

#: Decides one answer from the request's JSON body: an assistant message as a dict.
Respond = Callable[[Dict[str, Any]], Dict[str, Any]]


class ChatServer:
    """A running server: where it is, and what it was sent."""

    def __init__(self, respond: Respond, delay: float) -> None:
        self.respond  = respond
        self.delay    = delay
        self.base_url = ""
        #: The bearer key of every request, in the order they arrived.
        self.keys     : List[Optional[str]] = []
        #: The open connections, closed with the server: a kept-alive one would hold it open.
        self.writers  : List[asyncio.StreamWriter] = []

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self.writers.append(writer)
        try:
            while True:
                head = await reader.readuntil(b"\r\n\r\n")
                lines   = head.decode("latin-1").split("\r\n")
                headers = {k.strip().lower(): v.strip()
                           for k, _, v in (line.partition(":") for line in lines[1:] if line)}
                body    = json.loads(await reader.readexactly(int(headers.get("content-length", "0"))))
                auth    = headers.get("authorization", "")
                self.keys.append(auth[len("Bearer "):] if auth.startswith("Bearer ") else None)
                if self.delay:
                    await asyncio.sleep(self.delay)
                answer  = self.respond(body)
                if "error" in answer:
                    text    = answer["error"].replace("{key}", self.keys[-1] or "")
                    payload = json.dumps({"error": {"message": text, "type": "invalid_request_error",
                                                    "code": "invalid_api_key"}}).encode()
                    writer.write(b"HTTP/1.1 401 Unauthorized\r\nContent-Type: application/json\r\n"
                                 b"Content-Length: %d\r\n\r\n%s" % (len(payload), payload))
                    await writer.drain()
                    continue
                message = {"role": "assistant", "content": None, **answer}
                payload = json.dumps({
                    "id": "chatcmpl-1", "object": "chat.completion", "created": 0, "model": body["model"],
                    "choices": [{"index": 0, "message": message, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                }).encode()
                writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
                             b"Content-Length: %d\r\n\r\n%s" % (len(payload), payload))
                await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionError):
            pass
        finally:
            writer.close()


def answers(text: str) -> Respond:
    """Answers *text* to every request."""
    return lambda body: {"content": text}


def refuses() -> Respond:
    """Refuses every request with a 401 whose message echoes the key it was sent, as some servers do."""
    return lambda body: {"error": "Incorrect API key provided: {key}"}


def calls_then(tool: str, args: Dict[str, Any], text: str) -> Respond:
    """Calls *tool* with *args* until a tool result is in the request, then answers *text*."""
    def respond(body: Dict[str, Any]) -> Dict[str, Any]:
        if any(m.get("role") == "tool" for m in body["messages"]):
            return {"content": text}
        return {"tool_calls": [{"id": "call-1", "type": "function",
                                "function": {"name": tool, "arguments": json.dumps(args)}}]}
    return respond


@contextlib.asynccontextmanager
async def serve_chat(respond: Respond = answers("fine"), delay: float = 0.0) -> AsyncIterator[ChatServer]:
    """
    Serves chat completions on ``127.0.0.1`` at a free port while the block runs.

    Args:
        respond: What each request is answered with.
        delay: Seconds each answer waits, so two requests can overlap.

    Yields:
        ChatServer: With ``base_url`` (ending in ``/v1``) and ``keys``.
    """
    server = ChatServer(respond, delay)
    tcp    = await asyncio.start_server(server.handle, "127.0.0.1", 0)
    server.base_url = "http://127.0.0.1:%d/v1" % tcp.sockets[0].getsockname()[1]
    try:
        yield server
    finally:
        tcp.close()
        for writer in server.writers:
            writer.close()
        await asyncio.wait_for(tcp.wait_closed(), 5)
