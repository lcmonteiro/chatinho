# Design

## Context

See proposal.md for why. Today `_say_for` writes the routed peer into `msg.to` (`session.py`, `msg.to = self._answerer_of(frm, reply_to)`), and `_post` builds the audience from `msg.to`, minus a waiting ask and minus messages posted with `answer=True`. Four other places read `to`:

- `MessageStore`/`is_broadcast`: `to is None`.
- `Query.select`, the `peer` filter: `m.frm == peer or m.to == peer or m.reply_to in from_`. The default memory of `OpenAIConnector` and `AgentConnector` is `Query(peer=SELF, errors=False).last(20)`.
- `AgentConnector._history`: its own questions are `m.frm == me and m.to is not None and m.reply_to is None`. These are always explicit asks, so they are unaffected.
- `DatabaseBackend`: archives and reloads `to` in the `messages` table. That table has no other version, and the backend has no migrations; `create_all` creates missing tables but never alters an existing one.

## Goals / Non-Goals

**Goals:**
- A say keeps the speaker's addressing; the session's routing decision is recorded beside it, not over it.
- One field decides who is asked, so the `answer` flag on `_post` can go.
- A peer's memory keeps the questions it was asked, across a restart.

**Non-Goals:**
- Changing which peer a say is routed to (the rules from #37 stay as they are).
- A general migration framework for the archive.

## Decisions

### 1. `asked_of` is a field on `ChatMessage`, set where the message is made

The session could keep "who was asked" in a side map keyed by message id. But `Query` and the archive both need it, and both work on `ChatMessage` values. A field keeps the message plain data that a backend can store and a query can read. It defaults to None, so every message built elsewhere (answers, error replies, invocations, command results, reloaded history) is asked of nobody without anyone having to say so.

Set in exactly two places:
- `_ask_for`: `asked_of = to`.
- `_say_for`: `asked_of = to` when `to` is given, else `self._answerer_of(frm, reply_to)` for a peer's say (never for `TOOL`). `to` is left as the caller gave it.

### 2. The audience is `{asked_of}`, and the `answer` flag goes

```python
audience = {msg.asked_of} if msg.asked_of is not None and not resolved else set()
```

An answer is built with `asked_of=None`, so it reaches nobody's `answer` without a flag. The `resolved` check stays: a late answer said with `reply_to` may be routed to the question's author by the reply rule and also resolve a waiting ask, and the waiting asker already holds it. The depth bookkeeping (`self._depth[msg.id]` when the audience is not empty) is unchanged.

**Alternative rejected: keep `to` as the routing and add a "routed" flag that makes `is_broadcast` true.** It changes less code, because `Query` and the archive already use `to`. But `to` would no longer mean what the speaker chose, which is the confusion this change removes. Chosen with the user.

### 3. `AgentConnector.listen` skips what it is asked

The guard becomes `if not (msg.is_broadcast and msg.is_local) or msg.asked_of == self.peer_id: return`. Without it, a lone `AgentConnector` would get the user's say twice, now that the say is a broadcast: once in `answer` and once in `listen`. It would run the model twice and post two replies.

### 4. `Query(peer=)` adds `m.asked_of == peer`

That is the one-line change. `to == peer` stays, for addressed messages and for answers addressed back to the peer.

### 5. The archive gets an `asked_of` column, added in place

`ArchivedMessage.asked_of = Column(Integer, nullable=True)`, written by `_write` and read by `_read`. In `initialize()`, after `create_all`, the backend inspects the `messages` table. If `asked_of` is missing, it runs `ALTER TABLE messages ADD COLUMN asked_of INTEGER`. That is standard SQL, valid on SQLite and on the other databases SQLAlchemy targets. It only adds a nullable column, so existing rows load with `asked_of` None.

**Alternative rejected: Alembic.** It is a new dependency and a migrations directory for one nullable column. If the schema keeps changing, it becomes worth it.

**Alternative rejected (chosen with the user): widen `Query(peer=)` to include the messages a peer replied to, instead of storing `asked_of`.** It avoids the schema change, but a question that was never answered would drop out of memory after a restart, and it changes what `peer` means for every query, not just this case.

## Risks / Trade-offs

- [A third-party peer read `msg.to` in `listen` to tell whether a routed say was for it] → It reads `msg.asked_of` now. The proposal marks this as breaking. Nothing in the library or the examples relies on it.
- [The in-place `ALTER TABLE` runs on a database another process is writing] → It runs once, in `initialize()`, before the backend reads or writes. Concurrent writers to one archive were never supported.
- [Rows archived before the upgrade have no `asked_of`] → They load with `asked_of` None, as the spec says. Questions routed before the upgrade are in a peer's memory only if they were addressed, which is no worse than before #37 introduced routing.

## Migration Plan

Code and tests land in one change. An existing database is upgraded the first time the new backend starts. Rolling back the code leaves an unused nullable column, which the old code ignores, because it names its columns explicitly.
