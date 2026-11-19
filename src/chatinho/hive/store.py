"""
Everything the hive keeps, in one SQL database: chats, admin keys, messages, attachments, traces.

Plain synchronous SQLAlchemy; the app calls it from a thread pool. Messages
and traces are kept as the wire writes them, per chat, and a resend of one
already kept is skipped.
"""

import json
import re
import threading
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import (Column, DateTime, ForeignKey, Integer, LargeBinary, String, Text,
                        create_engine, delete, event, func, select)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

#: A chat's name: what the page shows and what a key is made for.
NAME = re.compile(r"[a-z0-9_-]{1,64}")


class NameTaken(ValueError):
    """A chat by that name already exists."""


@dataclass(frozen=True)
class Caller:
    """
    Who a key belongs to.

    Attributes:
        admin: Whether it is an admin key.
        chat: The chat's name, for a chat key; None for an admin.
    """

    admin : bool
    chat  : Optional[str] = None


class _Base(DeclarativeBase):
    pass


class _Chat(_Base):
    __tablename__ = "chats"

    id       = Column(Integer, primary_key=True)
    name     = Column(String(64), unique=True, nullable=False)
    key_hash = Column(String(64), unique=True, nullable=False)
    created  = Column(DateTime, nullable=False, default=datetime.now)


class _Admin(_Base):
    __tablename__ = "admins"

    id       = Column(Integer, primary_key=True)
    key_hash = Column(String(64), unique=True, nullable=False)
    created  = Column(DateTime, nullable=False, default=datetime.now)


class _Message(_Base):
    __tablename__ = "messages"

    chat_id   = Column(Integer, ForeignKey("chats.id", ondelete="CASCADE"), primary_key=True)
    id        = Column(String(64), primary_key=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    written   = Column(DateTime, nullable=False, default=datetime.now)
    wire      = Column(Text, nullable=False)


class _Attachment(_Base):
    __tablename__ = "attachments"

    chat_id    = Column(Integer, ForeignKey("chats.id", ondelete="CASCADE"), primary_key=True)
    msg_id     = Column(String(64), primary_key=True)
    name       = Column(String(255), primary_key=True)
    media_type = Column(String(255), nullable=False)
    data       = Column(LargeBinary, nullable=False)


class _Trace(_Base):
    __tablename__ = "traces"

    chat_id   = Column(Integer, ForeignKey("chats.id", ondelete="CASCADE"), primary_key=True)
    id        = Column(String(64), primary_key=True)
    msg_id    = Column(String(64), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False)
    seq       = Column(Integer, nullable=False)
    wire      = Column(Text, nullable=False)


class Store:
    """
    The hive's database.

    Args:
        db_url: Any URL SQLAlchemy accepts; the tables are made when missing.
    """

    def __init__(self, db_url: str) -> None:
        sqlite = db_url.startswith("sqlite")
        kwargs : Dict[str, Any] = {"connect_args": {"check_same_thread": False}} if sqlite else {}
        self._engine : Engine = create_engine(db_url, **kwargs)
        if sqlite:
            event.listen(self._engine, "connect", _sqlite_foreign_keys)
        _Base.metadata.create_all(self._engine)
        self._sessions = sessionmaker(self._engine, expire_on_commit=False)
        # SQLite takes one writer at a time; a lock keeps the thread pool from tripping on it.
        self._write    = threading.Lock()

    def close(self) -> None:
        """Closes the connections."""
        self._engine.dispose()

    # === Chats and keys =============================================================

    # @req REQ-HIVE-001
    def add_chat(self, name: str, key_hash: str) -> None:
        """
        Makes chat *name*, known by *key_hash*.

        Raises:
            ValueError: If *name* is not 1 to 64 of ``a-z 0-9 - _``.
            NameTaken: If a chat already has *name*.
        """
        if not isinstance(name, str) or not NAME.fullmatch(name):
            raise ValueError("A chat's name is 1 to 64 of a-z, 0-9, - and _, got %r" % (name,))
        with self._writing() as session:
            if session.scalar(select(_Chat.id).where(_Chat.name == name)) is not None:
                raise NameTaken("The name %r is taken" % name)
            session.add(_Chat(name=name, key_hash=key_hash))

    # @req REQ-HIVE-001
    def remove_chat(self, name: str) -> bool:
        """Deletes chat *name* and everything kept for it; False when there was none."""
        with self._writing() as session:
            chat = session.scalar(select(_Chat.id).where(_Chat.name == name))
            if chat is None:
                return False
            for table in (_Message, _Attachment, _Trace):
                session.execute(delete(table).where(table.chat_id == chat))
            session.execute(delete(_Chat).where(_Chat.id == chat))
            return True

    # @req REQ-HIVE-001, REQ-HIVE-006
    def chats(self) -> List[Dict[str, Any]]:
        """Every chat: ``name``, ``created``, ``messages`` (how many) and ``last`` (last write, or None)."""
        with self._sessions() as session:
            counted = (select(_Chat.name, _Chat.created, func.count(_Message.id), func.max(_Message.written))
                       .outerjoin(_Message, _Message.chat_id == _Chat.id)
                       .group_by(_Chat.id).order_by(_Chat.name))
            return [{"name": name, "created": created.isoformat(), "messages": int(count),
                     "last": None if last is None else last.isoformat()}
                    for name, created, count, last in session.execute(counted)]

    # @req REQ-HIVE-002
    def add_admin(self, key_hash: str) -> None:
        """Makes an admin known by *key_hash*."""
        with self._writing() as session:
            session.add(_Admin(key_hash=key_hash))

    # @req REQ-HIVE-003
    def who(self, key_hash: str) -> Optional[Caller]:
        """Who *key_hash* belongs to, or None."""
        with self._sessions() as session:
            if session.scalar(select(_Admin.id).where(_Admin.key_hash == key_hash)) is not None:
                return Caller(admin=True)
            name = session.scalar(select(_Chat.name).where(_Chat.key_hash == key_hash))
            return None if name is None else Caller(admin=False, chat=name)

    def has_chat(self, name: str) -> bool:
        """Whether chat *name* exists."""
        with self._sessions() as session:
            return session.scalar(select(_Chat.id).where(_Chat.name == name)) is not None

    # === A chat's records ===========================================================

    # @req REQ-HIVE-004
    def put_messages(self, chat: str, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Keeps *messages* in *chat*; returns those that were new, in the order given."""
        with self._writing() as session:
            at    = self._chat_id(session, chat)
            known = self._known(session, _Message, at, [m["id"] for m in messages])
            new   = []
            for message in messages:
                if message["id"] in known:
                    continue
                known.add(message["id"])
                session.add(_Message(chat_id=at, id=message["id"], wire=json.dumps(message),
                                     timestamp=datetime.fromisoformat(message["timestamp"])))
                new.append(message)
            return new

    # @req REQ-HIVE-004, REQ-HIVE-006
    def messages(
        self, chat: str, since: Optional[datetime] = None, limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """*chat*'s messages, oldest first: those from *since* on, the last *limit* of them."""
        with self._sessions() as session:
            query = select(_Message.wire).where(_Message.chat_id == self._chat_id(session, chat))
            if since is not None:
                query = query.where(_Message.timestamp >= since)
            if limit is not None:
                rows = list(session.scalars(query.order_by(_Message.timestamp.desc()).limit(limit)))
                rows.reverse()
            else:
                rows = list(session.scalars(query.order_by(_Message.timestamp.asc())))
            return [json.loads(wire) for wire in rows]

    # @req REQ-HIVE-004
    def forget(self, chat: str, before: Optional[datetime] = None) -> int:
        """Drops *chat*'s messages older than *before*, with their attachments and traces."""
        with self._writing() as session:
            at    = self._chat_id(session, chat)
            query = select(_Message.id).where(_Message.chat_id == at)
            if before is not None:
                query = query.where(_Message.timestamp < before)
            gone = list(session.scalars(query))
            for start in range(0, len(gone), 500):
                some = gone[start:start + 500]
                session.execute(delete(_Attachment).where(_Attachment.chat_id == at,
                                                          _Attachment.msg_id.in_(some)))
                session.execute(delete(_Trace).where(_Trace.chat_id == at, _Trace.msg_id.in_(some)))
                session.execute(delete(_Message).where(_Message.chat_id == at, _Message.id.in_(some)))
            return len(gone)

    # @req REQ-HIVE-005
    def put_attachment(self, chat: str, msg_id: str, name: str, media_type: str, data: bytes) -> None:
        """Keeps one attachment; a second with the same name replaces the first."""
        with self._writing() as session:
            session.merge(_Attachment(chat_id=self._chat_id(session, chat), msg_id=msg_id, name=name,
                                      media_type=media_type, data=data))

    # @req REQ-HIVE-005
    def attachment(self, chat: str, msg_id: str, name: str) -> Optional[Tuple[str, bytes]]:
        """The media type and bytes of one attachment, or None."""
        with self._sessions() as session:
            row = session.get(_Attachment, (self._chat_id(session, chat), msg_id, name))
            return None if row is None else (str(row.media_type), bytes(row.data))

    # @req REQ-HIVE-005
    def put_traces(self, chat: str, traces: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Keeps *traces* in *chat*; returns those that were new, in the order given."""
        with self._writing() as session:
            at    = self._chat_id(session, chat)
            known = self._known(session, _Trace, at, [t["id"] for t in traces])
            seq   = session.scalar(select(func.max(_Trace.seq)).where(_Trace.chat_id == at)) or 0
            new   = []
            for trace in traces:
                if trace["id"] in known:
                    continue
                known.add(trace["id"])
                seq += 1
                session.add(_Trace(chat_id=at, id=trace["id"], msg_id=trace["msg_id"], seq=seq,
                                   timestamp=datetime.fromisoformat(trace["timestamp"]),
                                   wire=json.dumps(trace)))
                new.append(trace)
            return new

    # @req REQ-HIVE-006
    def traces(self, chat: str, msg_id: str) -> List[Dict[str, Any]]:
        """The traces of *msg_id* in *chat*, oldest first, then in the order they arrived."""
        with self._sessions() as session:
            at   = self._chat_id(session, chat)
            rows = session.scalars(select(_Trace.wire)
                                   .where(_Trace.chat_id == at, _Trace.msg_id == msg_id)
                                   .order_by(_Trace.timestamp.asc(), _Trace.seq.asc()))
            return [json.loads(wire) for wire in rows]

    def has_message(self, chat: str, msg_id: str) -> bool:
        """Whether *chat* holds message *msg_id*, or any trace of it."""
        with self._sessions() as session:
            at = self._chat_id(session, chat)
            if session.get(_Message, (at, msg_id)) is not None:
                return True
            return session.scalar(select(_Trace.id).where(_Trace.chat_id == at, _Trace.msg_id == msg_id)
                                  .limit(1)) is not None

    # === Inside =====================================================================

    @staticmethod
    def _chat_id(session: Session, name: str) -> int:
        at = session.scalar(select(_Chat.id).where(_Chat.name == name))
        if at is None:
            raise KeyError(name)
        return int(at)

    @staticmethod
    def _known(session: Session, table: Any, chat: int, ids: List[str]) -> set:
        known : set = set()
        for start in range(0, len(ids), 500):
            known.update(session.scalars(select(table.id).where(table.chat_id == chat,
                                                                table.id.in_(ids[start:start + 500]))))
        return known

    def _writing(self) -> "_Writing":
        return _Writing(self)


class _Writing:
    """A session that commits on success, under the store's write lock."""

    def __init__(self, store: Store) -> None:
        self._store   = store
        self._session : Optional[Session] = None

    def __enter__(self) -> Session:
        self._store._write.acquire()
        self._session = self._store._sessions()
        return self._session

    def __exit__(self, kind: Any, exc: Any, tb: Any) -> None:
        assert self._session is not None
        try:
            if kind is None:
                self._session.commit()
            else:
                self._session.rollback()
        finally:
            self._session.close()
            self._store._write.release()


def _sqlite_foreign_keys(connection: Any, record: Any) -> None:
    cursor = connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
