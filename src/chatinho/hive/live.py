"""What is stored, handed to every stream open on its chat."""

import asyncio
from typing import Any, AsyncIterator, Dict, List, Tuple

#: One event: its kind (``message`` or ``trace``) and its wire data.
Event = Tuple[str, Dict[str, Any]]


# @req REQ-HIVE-007
class Live:
    """
    One queue per open stream; what a chat stores is put on each of its chat's queues.

    Everything runs on the app's event loop: a route stores off the loop, then
    publishes on it, so no lock is needed.
    """

    def __init__(self) -> None:
        self._streams : Dict[str, List["asyncio.Queue[Event]"]] = {}

    def subscribe(self, chat: str) -> "asyncio.Queue[Event]":
        """A queue that receives what *chat* stores from now on."""
        queue : "asyncio.Queue[Event]" = asyncio.Queue()
        self._streams.setdefault(chat, []).append(queue)
        return queue

    def unsubscribe(self, chat: str, queue: "asyncio.Queue[Event]") -> None:
        """Stops feeding *queue*."""
        queues = self._streams.get(chat, [])
        if queue in queues:
            queues.remove(queue)
        if not queues:
            self._streams.pop(chat, None)

    def publish(self, chat: str, kind: str, data: Dict[str, Any]) -> None:
        """Hands one stored record to every stream on *chat*."""
        for queue in self._streams.get(chat, []):
            queue.put_nowait((kind, data))

    async def events(self, chat: str) -> AsyncIterator[Event]:
        """Every event *chat* stores from now on, until the caller stops."""
        queue = self.subscribe(chat)
        try:
            while True:
                yield await queue.get()
        finally:
            self.unsubscribe(chat, queue)
