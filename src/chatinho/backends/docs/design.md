# Design: backends

## Overview

`backends` holds the archive: `DatabaseBackend` in `database.py`, behind
`chatinho[sql]`. It is a peer, `@backend("database")`, that declares
`HookListen` to hear the whole conversation and write every message,
`HookLoad` to give it back when a session starts, `HookForget` to drop it,
and `HookKeep`/`HookLink` to store what messages attach and hand back a
`file://` link to it. It keeps two tables, `messages` and `attachments`, in
any database SQLAlchemy reaches.

![The archive and how the session reaches it (REQ-BACK-001, REQ-BACK-002, REQ-BACK-003, REQ-BACK-004, REQ-BACK-007)](diagrams/backends-blocks.svg)

## Decisions

- **The archive is a peer that listens, not a store the session pushes at**
  (REQ-BACK-001, REQ-BACK-005). The conversation crosses it as it crosses
  anyone, and the session asks whoever declared `HookLoad` for the older
  tier at `start()`, so a chat reopens where it left off. (baseline-backends)
- **All database work runs on one thread of its own** (REQ-BACK-001,
  REQ-BACK-004). SQLAlchemy is synchronous, so nothing runs on the loop; and
  the session delivers messages concurrently while an in-memory SQLite is
  one shared connection (`StaticPool`, `check_same_thread` off), so a single
  worker runs every call whole and in order. (baseline-backends)
- **A message's id is its primary key** (REQ-BACK-001, REQ-BACK-005). Ids are
  unique across chats, so hearing a message again is a merge, not a second
  row, and a reopened chat never overwrites what it archived.
  (baseline-backends)
- **The status is archived** (REQ-BACK-001). Without it a failed reply came
  back from a reopened archive as an answer and reached a model's memory.
  (baseline-backends)
- **Old archives are read as they are, never migrated** (REQ-BACK-008). A
  table that still has the `asked_of` column loads and saves; the column is
  left unread. (baseline-backends)
- **Attachments are rows; a file exists only when linked** (REQ-BACK-007).
  `(msg_id, name)` is the key, so keeping twice is a no-op. The file is
  written on the first `link`, under a quoted and prefixed name so no name
  leaves its folder and `.`/`..` are files, into a temporary directory
  removed at `shutdown()`. `forget` drops a message's attachments with it
  (REQ-BACK-003). (baseline-backends)
- **An unknown keyword is an error** (REQ-BACK-004). `ecoh=True` used to be
  swallowed into a config nothing read. (baseline-backends)

## Interfaces

- `DatabaseBackend(database_url: str, echo: bool = False)`: `@backend("database")`,
  declaring `HookListen`, `HookLoad`, `HookForget`, `HookKeep` and `HookLink`.
  - `initialize()`: opens the engine, starts the worker, creates the tables.
  - `shutdown()`: stops the worker, disposes of the engine, removes the
    linked files.
  - `async listen(msg: ChatMessage) -> None`
  - `async load(since: Optional[datetime] = None, limit: Optional[int] = None) -> List[ChatMessage]`:
    oldest first; `limit` keeps the newest that many.
  - `async forget(before: Optional[datetime] = None) -> int`: how many
    messages were dropped.
  - `async keep(msg_id: MessageID, attachments: Sequence[Attachment]) -> None`
  - `async link(msg_id: MessageID, name: str) -> Optional[str]`: a `file://`
    URI, or `None` for a name never kept.
- Tables: `messages` (`id`, `text`, `frm`, `to`, `reply_to`, `timestamp`,
  `status`) and `attachments` (`msg_id`, `name`, `media_type`, `data`).
- Errors: `RuntimeError` when used before `initialize()`; `TypeError` for an
  unknown constructor keyword.

## Constraints

- A specialization: it imports the framework only, never another
  specialization (`tests/test_architecture.py`).
- `sqlalchemy` is imported only here, behind `chatinho[sql]`.
- Nothing blocks the loop: every SQLAlchemy call runs on the worker thread.
- The session's `context()` is synchronous, so what a session sees is what
  `load` returned at `start()`, bounded by `recall` (REQ-BACK-005).
