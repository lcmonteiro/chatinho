"""
Where ``HiveBackend`` keeps what waits to be sent, and, with a cache, a copy of the chat.

An :class:`Outbox` is the queue the sender takes from in order. Without a
cache it lives in memory; with one it is a table of :class:`HiveCache`, a
SQLite file that also keeps the chat's messages and attachments. Standard
library only; every call blocks, so ``HiveBackend`` makes them on a thread.
"""

import collections
import json
import sqlite3
import threading
from datetime import datetime
from typing import Any, Deque, Dict, List, Optional, Protocol, Tuple

#: One item of the outbox: its kind (``message``, ``attachment`` or ``trace``) and its payload.
Item = Tuple[str, Dict[str, Any]]


class Outbox(Protocol):
    """What waits to reach the hive, oldest first."""

    def put(self, item: Item) -> int:
        """Adds *item* at the end; returns how many of the oldest were dropped to make room."""
        ...

    def peek(self, n: int) -> List[Item]:
        """The oldest *n* items, left in place."""
        ...

    def drop(self, n: int) -> None:
        """Removes the oldest *n* items, once the hive has them."""
        ...

    def __len__(self) -> int:
        ...


# @req REQ-BACK-011
class MemoryOutbox:
    """An outbox in memory, bounded by *limit*."""

    def __init__(self, limit: int) -> None:
        self._limit = limit
        self._items : Deque[Item] = collections.deque()

    def put(self, item: Item) -> int:
        self._items.append(item)
        dropped = 0
        while len(self._items) > self._limit:
            self._items.popleft()
            dropped += 1
        return dropped

    def peek(self, n: int) -> List[Item]:
        return [self._items[i] for i in range(min(n, len(self._items)))]

    def drop(self, n: int) -> None:
        for _ in range(min(n, len(self._items))):
            self._items.popleft()

    def __len__(self) -> int:
        return len(self._items)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta        (name TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS messages    (id TEXT PRIMARY KEY, timestamp TEXT NOT NULL, wire TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS messages_at ON messages (timestamp);
CREATE TABLE IF NOT EXISTS attachments (msg_id TEXT NOT NULL, name TEXT NOT NULL, media_type TEXT NOT NULL,
                                        data BLOB NOT NULL, PRIMARY KEY (msg_id, name));
CREATE TABLE IF NOT EXISTS outbox      (seq INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL,
                                        payload TEXT NOT NULL);
"""


# @req REQ-BACK-013
class HiveCache:
    """
    A local SQLite file holding a copy of the chat and the outbox, for the hive at *url*.

    Args:
        path: The file; made when missing.
        url: The hive the cache belongs to.
        limit: The most items its outbox holds.

    Raises:
        ValueError: If the file was made for another hive's URL.
    """

    def __init__(self, path: str, url: str, limit: int) -> None:
        self.path   = path
        self._lock  = threading.Lock()
        self._db    = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._db.executescript(_SCHEMA)
        row = self._db.execute("SELECT value FROM meta WHERE name = 'url'").fetchone()
        if row is None:
            self._db.execute("INSERT INTO meta (name, value) VALUES ('url', ?)", (url,))
        elif row[0] != url:
            self._db.close()
            raise ValueError("The cache %s was made for the hive at %s, not %s" % (path, row[0], url))
        self._outbox = _CacheOutbox(self, limit)

    @property
    def outbox(self) -> Outbox:
        """The outbox kept in the file."""
        return self._outbox

    def put_messages(self, messages: List[Dict[str, Any]]) -> None:
        """Keeps *messages*, as the wire writes them; one already kept is left as it is."""
        with self._lock:
            self._db.executemany("INSERT OR IGNORE INTO messages (id, timestamp, wire) VALUES (?, ?, ?)",
                                 [(m["id"], m["timestamp"], json.dumps(m)) for m in messages])

    def messages(
        self, since: Optional[datetime] = None, limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """The kept messages, oldest first, narrowed as ``load`` narrows."""
        where, args = ("WHERE timestamp >= ?", [since.isoformat()]) if since is not None else ("", [])
        with self._lock:
            if limit is not None:
                newest = "SELECT wire FROM messages %s ORDER BY timestamp DESC LIMIT ?" % where
                rows   = self._db.execute(newest, args + [limit]).fetchall()
                rows.reverse()
            else:
                rows = self._db.execute("SELECT wire FROM messages %s ORDER BY timestamp ASC" % where,
                                        args).fetchall()
        return [json.loads(wire) for (wire,) in rows]

    def forget(self, before: Optional[datetime] = None) -> int:
        """Drops the messages older than *before* and their attachments; returns how many went."""
        where, args = ("WHERE timestamp < ?", [before.isoformat()]) if before is not None else ("", [])
        with self._lock:
            self._db.execute("BEGIN")
            self._db.execute("DELETE FROM attachments WHERE msg_id IN (SELECT id FROM messages %s)" % where,
                             args)
            gone = self._db.execute("DELETE FROM messages %s" % where, args).rowcount
            self._db.execute("COMMIT")
        return int(gone)

    def put_attachment(self, msg_id: str, name: str, media_type: str, data: bytes) -> None:
        """Keeps one attachment of *msg_id*."""
        with self._lock:
            self._db.execute("INSERT OR REPLACE INTO attachments (msg_id, name, media_type, data) "
                             "VALUES (?, ?, ?, ?)", (msg_id, name, media_type, data))

    def attachment(self, msg_id: str, name: str) -> Optional[Tuple[str, bytes]]:
        """The media type and bytes of attachment *name* of *msg_id*, or None."""
        with self._lock:
            row = self._db.execute("SELECT media_type, data FROM attachments WHERE msg_id = ? AND name = ?",
                                   (msg_id, name)).fetchone()
        return None if row is None else (str(row[0]), bytes(row[1]))

    def close(self) -> None:
        """Closes the file."""
        with self._lock:
            self._db.close()


_DROP_OLDEST = "DELETE FROM outbox WHERE seq IN (SELECT seq FROM outbox ORDER BY seq LIMIT ?)"


class _CacheOutbox:
    """The outbox table of a :class:`HiveCache`: it outlives the run that filled it."""

    def __init__(self, cache: HiveCache, limit: int) -> None:
        self._cache = cache
        self._limit = limit

    def put(self, item: Item) -> int:
        kind, payload = item
        with self._cache._lock:
            db = self._cache._db
            db.execute("BEGIN")
            db.execute("INSERT INTO outbox (kind, payload) VALUES (?, ?)", (kind, json.dumps(payload)))
            over = db.execute("SELECT COUNT(*) FROM outbox").fetchone()[0] - self._limit
            if over > 0:
                db.execute(_DROP_OLDEST, (over,))
            db.execute("COMMIT")
        return max(over, 0)

    def peek(self, n: int) -> List[Item]:
        with self._cache._lock:
            rows = self._cache._db.execute("SELECT kind, payload FROM outbox ORDER BY seq LIMIT ?",
                                           (n,)).fetchall()
        return [(kind, json.loads(payload)) for kind, payload in rows]

    def drop(self, n: int) -> None:
        with self._cache._lock:
            self._cache._db.execute(_DROP_OLDEST,
                                    (n,))

    def __len__(self) -> int:
        with self._cache._lock:
            return int(self._cache._db.execute("SELECT COUNT(*) FROM outbox").fetchone()[0])
