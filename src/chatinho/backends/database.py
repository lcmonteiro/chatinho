"""The older tier of the conversation, kept in a SQL database.

The backend is not a key-value store: it is where messages go when they are no
longer recent. Nobody asks it directly — a participant asks the session for
context, and the session is what reaches down here, recalling a window at
startup and archiving each message as it is said.

Every method is a coroutine and every one of them runs its SQLAlchemy work in
an executor, because SQLAlchemy is synchronous and the chat's whole promise is
that one slow subsystem holds up nobody but itself.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, List, Optional

from sqlalchemy import Column, DateTime, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool

from ..chat_hooks import HookArchive, HookForget, HookRecall, backend, require
from ..chat_message import ChatMessage

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Declarative base for the backend's models."""


class ArchivedMessage(Base):
    """One archived message, addressed exactly as it was when it was said.

    ``id`` is the message's own id and the primary key: it is unique within a
    chat, it is what a reply points at, and it is what makes archiving the same
    message twice a no-op rather than a duplicate row.
    """

    __tablename__ = "messages"

    id        = Column(String, primary_key=True)
    text      = Column(Text, nullable=False)
    frm       = Column(Integer, nullable=False)
    to        = Column(Integer, nullable=True)
    reply_to  = Column(String, nullable=True)
    timestamp = Column(DateTime(timezone=False), nullable=False, index=True)


@backend("database")
@require(HookArchive)
@require(HookRecall)
@require(HookForget)
class DatabaseBackend:
    """Keeps the conversation in a SQL database, one row per message."""

    def __init__(self, database_url: str, echo: bool = False, **kwargs: Any) -> None:
        """Prepares the backend; the connection opens in :meth:`initialize`.

        Args:
            database_url: Any URL SQLAlchemy accepts.
            echo: Whether SQLAlchemy logs the statements it runs.
            **kwargs: Kept for callers that pass extra configuration.
        """
        self.config       = kwargs
        self.database_url = database_url
        self.echo         = echo
        self.engine       : Optional[Any] = None
        self.SessionLocal : Optional[Any] = None

    # === Lifecycle ==================================================================

    def initialize(self) -> None:
        """Opens the connection and creates the table if it is not there.

        Every call runs in an executor thread, so SQLite is opened with
        ``check_same_thread`` off; and an in-memory database is one database
        *per connection*, so it is pinned to a single shared one — otherwise
        the thread that writes and the thread that reads see different tables,
        which is exactly what the first run of this backend did.
        """
        logger.info("Opening the message archive at %s", self.database_url)
        options : dict = {"echo": self.echo, "future": True}
        if self.database_url.startswith("sqlite"):
            options["connect_args"] = {"check_same_thread": False}
            if ":memory:" in self.database_url or "mode=memory" in self.database_url:
                options["poolclass"] = StaticPool
        self.engine = create_engine(self.database_url, **options)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, future=True)

    def shutdown(self) -> None:
        """Disposes of the engine, so its pool does not outlive the chat."""
        if self.engine is not None:
            self.engine.dispose()
            self.engine = None
            self.SessionLocal = None

    # === The archive ================================================================

    async def archive(self, messages: List[ChatMessage]) -> None:
        """Writes *messages* to the archive, replacing any already there.

        Args:
            messages: What to keep, in the order it was said.
        """
        await self._off_loop(self._archive, messages)

    async def recall(
        self,
        since : Optional[datetime] = None,
        limit : Optional[int] = None,
    ) -> List[ChatMessage]:
        """Reads the tail of the archive back, oldest first.

        Args:
            since: Keep only messages stamped at or after this moment.
            limit: At most this many, counting back from the newest.

        Returns:
            List[ChatMessage]: Rebuilt messages, oldest first.
        """
        return await self._off_loop(self._recall, since, limit)

    async def forget(self, before: Optional[datetime] = None) -> int:
        """Drops archived messages older than *before*, or all of them.

        Args:
            before: Keep everything from this moment on; None forgets the lot.

        Returns:
            int: How many rows were dropped.
        """
        return await self._off_loop(self._forget, before)

    # === Internals ==================================================================

    @staticmethod
    async def _off_loop(work: Any, *args: Any) -> Any:
        """Runs *work* in an executor, so SQLAlchemy never blocks the loop."""
        return await asyncio.get_running_loop().run_in_executor(None, work, *args)

    def _session(self) -> Any:
        """Returns a database session.

        Raises:
            RuntimeError: If the backend was never initialized.
        """
        if self.SessionLocal is None:
            raise RuntimeError("Backend not initialized: call initialize() first")
        return self.SessionLocal()

    def _archive(self, messages: List[ChatMessage]) -> None:
        """The synchronous half of :meth:`archive`."""
        with self._session() as session:
            for msg in messages:
                session.merge(ArchivedMessage(
                    id=msg.id, text=msg.text, frm=msg.frm, to=msg.to,
                    reply_to=msg.reply_to, timestamp=msg.timestamp,
                ))
            session.commit()

    def _recall(self, since: Optional[datetime], limit: Optional[int]) -> List[ChatMessage]:
        """The synchronous half of :meth:`recall`."""
        with self._session() as session:
            query = session.query(ArchivedMessage)
            if since is not None:
                query = query.filter(ArchivedMessage.timestamp >= since)
            rows = query.order_by(ArchivedMessage.timestamp.desc()).limit(limit).all() \
                if limit is not None else query.order_by(ArchivedMessage.timestamp.asc()).all()
            if limit is not None:
                rows = list(reversed(rows))
            return [
                ChatMessage(id=r.id, text=r.text, frm=r.frm, to=r.to,
                            reply_to=r.reply_to, timestamp=r.timestamp)
                for r in rows
            ]

    def _forget(self, before: Optional[datetime]) -> int:
        """The synchronous half of :meth:`forget`."""
        with self._session() as session:
            query = session.query(ArchivedMessage)
            if before is not None:
                query = query.filter(ArchivedMessage.timestamp < before)
            dropped = query.delete(synchronize_session=False)
            session.commit()
            return int(dropped)
