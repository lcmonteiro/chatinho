"""
The hive's HTTP side: the API a chat's backend speaks, the admin views and stream, and the page.

Every route under ``/api`` needs a key in ``X-Hive-Key`` (the stream also takes
``?key=``): a chat key acts on its own chat, an admin key reads every chat.
"""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from importlib import resources
from typing import Any, AsyncIterator, Callable, Dict, List, Optional

from fastapi import Body, Depends, FastAPI, HTTPException, Query, Request, Response, Security
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.security import APIKeyHeader
from starlette.concurrency import run_in_threadpool

from ..support.parts.hive import KEY_HEADER, message_from_wire, message_to_wire
from ..support.parts.hive import trace_from_wire, trace_to_wire
from .keys import hash_key
from .live import Live
from .store import Caller, Store

logger = logging.getLogger(__name__)

_KEY = APIKeyHeader(name=KEY_HEADER, auto_error=False,
                    description="A chat's key acts on its own chat; an admin key reads every chat.")

#: How often a quiet stream sends a comment, so a closed connection is noticed.
HEARTBEAT : float = 15.0


# @req REQ-HIVE-003, REQ-HIVE-004, REQ-HIVE-005, REQ-HIVE-006, REQ-HIVE-007, REQ-HIVE-008, REQ-HIVE-009
def create_app(db_url: str) -> FastAPI:
    """
    The hive's application, over the database at *db_url*.

    Args:
        db_url: Any URL SQLAlchemy accepts.

    Returns:
        FastAPI: The app, with its routes, ``/docs`` and ``/openapi.json``.
    """
    store = Store(db_url)
    live  = Live()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        store.close()

    app = FastAPI(title="chatinho hive", lifespan=lifespan,
                  description="Where every chat is kept and seen: its messages, attachments and traces.")

    async def caller_of(key: Optional[str]) -> Caller:
        if not key:
            raise HTTPException(401, "A key is needed in %s" % KEY_HEADER)
        caller = await run_in_threadpool(store.who, hash_key(key))
        if caller is None:
            raise HTTPException(401, "Unknown key")
        return caller

    # @req REQ-HIVE-003
    async def a_chat(key: Optional[str] = Security(_KEY)) -> str:
        caller = await caller_of(key)
        if caller.chat is None:
            raise HTTPException(403, "This needs a chat's key")
        return caller.chat

    # @req REQ-HIVE-003
    async def an_admin(key: Optional[str] = Security(_KEY)) -> Caller:
        caller = await caller_of(key)
        if not caller.admin:
            raise HTTPException(403, "This needs an admin key")
        return caller

    async def known_chat(name: str) -> str:
        if not await run_in_threadpool(store.has_chat, name):
            raise HTTPException(404, "No chat %r" % name)
        return name

    # === A chat's own records ========================================================

    # @req REQ-HIVE-004
    @app.post("/api/messages", tags=["chat"], summary="Keep a batch of messages; a resend is skipped")
    async def post_messages(body: Dict[str, Any] = Body(...),
                            chat: str = Depends(a_chat)) -> Dict[str, int]:
        batch = _batch(body, "messages", lambda m: message_to_wire(message_from_wire(m), _name(m)))
        new   = await run_in_threadpool(store.put_messages, chat, batch)
        for message in new:
            live.publish(chat, "message", message)
        return {"stored": len(new)}

    # @req REQ-HIVE-004
    @app.get("/api/messages", tags=["chat"], summary="The chat's messages, oldest first")
    async def get_messages(since: Optional[datetime] = Query(None), limit: Optional[int] = Query(None, ge=0),
                           chat: str = Depends(a_chat)) -> Dict[str, List[Dict[str, Any]]]:
        return {"messages": await run_in_threadpool(store.messages, chat, since, limit)}

    # @req REQ-HIVE-004
    @app.delete("/api/messages", tags=["chat"],
                summary="Forget the messages before a time, and all they carried")
    async def forget(before: Optional[datetime] = Query(None), chat: str = Depends(a_chat)) -> Dict[str, int]:
        return {"forgotten": await run_in_threadpool(store.forget, chat, before)}

    # @req REQ-HIVE-005
    @app.put("/api/messages/{msg_id}/attachments/{name}", status_code=204, tags=["chat"],
             summary="Keep one attachment of a message; the body is its bytes")
    async def put_attachment(msg_id: str, name: str, request: Request,
                             chat: str = Depends(a_chat)) -> Response:
        media_type = request.headers.get("content-type", "application/octet-stream")
        await run_in_threadpool(store.put_attachment, chat, msg_id, name, media_type, await request.body())
        return Response(status_code=204)

    # @req REQ-HIVE-005
    @app.get("/api/messages/{msg_id}/attachments/{name}", tags=["chat"], summary="One attachment's bytes")
    async def get_attachment(msg_id: str, name: str, chat: str = Depends(a_chat)) -> Response:
        found = await run_in_threadpool(store.attachment, chat, msg_id, name)
        if found is None:
            raise HTTPException(404, "No attachment %r of %s" % (name, msg_id))
        media_type, data = found
        return Response(content=data, media_type=media_type)

    # @req REQ-HIVE-005
    @app.post("/api/traces", tags=["chat"], summary="Keep a batch of traces; a resend is skipped")
    async def post_traces(body: Dict[str, Any] = Body(...), chat: str = Depends(a_chat)) -> Dict[str, int]:
        batch = _batch(body, "traces", lambda t: trace_to_wire(trace_from_wire(t), _name(t)))
        new   = await run_in_threadpool(store.put_traces, chat, batch)
        for trace in new:
            live.publish(chat, "trace", trace)
        return {"stored": len(new)}

    # === What an admin sees ==========================================================

    # @req REQ-HIVE-006
    @app.get("/api/chats", tags=["admin"], summary="Every chat, with how many messages and its last write")
    async def chats(_: Caller = Depends(an_admin)) -> Dict[str, List[Dict[str, Any]]]:
        return {"chats": await run_in_threadpool(store.chats)}

    # @req REQ-HIVE-006
    @app.get("/api/chats/{name}/messages", tags=["admin"], summary="A chat's messages, oldest first")
    async def chat_messages(name: str, since: Optional[datetime] = Query(None),
                            limit: Optional[int] = Query(None, ge=0),
                            _: Caller = Depends(an_admin)) -> Dict[str, List[Dict[str, Any]]]:
        await known_chat(name)
        return {"messages": await run_in_threadpool(store.messages, name, since, limit)}

    # @req REQ-HIVE-006
    @app.get("/api/chats/{name}/messages/{msg_id}/traces", tags=["admin"],
             summary="A message's traces, oldest first, each with the trace it follows")
    async def message_traces(name: str, msg_id: str,
                             _: Caller = Depends(an_admin)) -> Dict[str, List[Dict[str, Any]]]:
        await known_chat(name)
        if not await run_in_threadpool(store.has_message, name, msg_id):
            raise HTTPException(404, "No message %s in %r" % (msg_id, name))
        return {"traces": await run_in_threadpool(store.traces, name, msg_id)}

    # @req REQ-HIVE-007
    @app.get("/api/chats/{name}/stream", tags=["admin"], response_class=StreamingResponse,
             summary="Server-sent events: every message and trace the chat stores from now on",
             description="Takes the admin key in %s or as ?key=, since a browser's EventSource sets "
                         "no headers." % KEY_HEADER)
    async def stream(name: str, key: Optional[str] = Query(None), header: Optional[str] = Security(_KEY)
                     ) -> StreamingResponse:
        caller = await caller_of(header or key)
        if not caller.admin:
            raise HTTPException(403, "This needs an admin key")
        await known_chat(name)
        return StreamingResponse(_events(live, name), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    # @req REQ-HIVE-008
    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def page() -> HTMLResponse:
        return HTMLResponse(_PAGE())

    app.state.store = store
    app.state.live  = live
    return app


def _name(data: Any) -> str:
    """The speaker's name a record was sent with; ``?`` when it came without one."""
    name = data.get("frm_name") if isinstance(data, dict) else None
    if name is not None and not isinstance(name, str):
        raise ValueError("'frm_name' must be a string")
    return name or "?"


def _batch(body: Any, field: str, read: Callable[[Any], Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Every record of *body*'s *field*, checked and written back; 422 when one is not a record."""
    items = body.get(field) if isinstance(body, dict) else None
    if not isinstance(items, list):
        raise HTTPException(422, "The body is {%r: [...]}" % field)
    try:
        return [read(item) for item in items]
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None


async def _events(live: Live, chat: str) -> AsyncIterator[str]:
    """The stream's text: an opening comment, then one event per record, and a comment when quiet."""
    queue = live.subscribe(chat)
    try:
        yield ": open\n\n"
        while True:
            try:
                kind, data = await asyncio.wait_for(queue.get(), HEARTBEAT)
            except asyncio.TimeoutError:
                yield ": still here\n\n"
                continue
            yield "event: %s\ndata: %s\n\n" % (kind, json.dumps(data))
    finally:
        live.unsubscribe(chat, queue)


def _PAGE() -> str:
    return resources.files("chatinho.hive").joinpath("page.html").read_text(encoding="utf-8")
