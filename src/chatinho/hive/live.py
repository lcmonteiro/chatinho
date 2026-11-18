"""What is stored, handed to every stream open on its chat."""

import asyncio
from typing import Any, AsyncIterator, Dict, Tuple

#: One event: its kind (``message`` or ``trace``) and its wire data.
Event = Tuple[str, Dict[str, Any]]


class Live:
    """One queue per open stream; what a chat stores is put on each of its chat's queues."""

    def __init__(self) -> None:
        raise NotImplementedError

    def subscribe(self, chat: str) -> "asyncio.Queue[Event]":
        """A queue that receives what *chat* stores from now on."""
        raise NotImplementedError

    def unsubscribe(self, chat: str, queue: "asyncio.Queue[Event]") -> None:
        """Stops feeding *queue*."""
        raise NotImplementedError

    def publish(self, chat: str, kind: str, data: Dict[str, Any]) -> None:
        """Hands one stored record to every stream on *chat*."""
        raise NotImplementedError

    async def events(self, chat: str) -> AsyncIterator[Event]:
        """Every event *chat* stores from now on, until the caller stops."""
        raise NotImplementedError
        yield ("", {})  # pragma: no cover - makes this an async generator
