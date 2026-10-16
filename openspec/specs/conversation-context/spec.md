# conversation-context Specification

## Purpose

Lets a peer ask for the part of the conversation it needs (a thread, what passed between it and one peer, nothing that failed) with a `Query` value that the session applies today and a backend could apply later.

## Requirements

### Requirement: A Query says which messages
chatinho SHALL provide `Query`, an immutable value with these fields, all optional and combined with AND:
- `peer`: the messages from that peer, to it, asked of it, or replying to one of its messages;
- `thread`: the reply chain of that message (the message, every message it replies to up to the root, and every reply to a message in that chain);
- `errors`: when False, replies whose status is `error` are left out;
- `since`: messages stamped at or after that moment;
- `limit`: at most that many, the newest.

`Query.last(n)` MUST return a copy with `limit=n`. A `Query` MUST be plain data (no callables), so a backend can translate it.

#### Scenario: Last twenty without errors
- **WHEN** a peer asks `context(Query(errors=False).last(20))` in a conversation of thirty messages, two of them error replies
- **THEN** it gets the twenty newest of the twenty-eight that are not errors, oldest first

#### Scenario: A thread
- **WHEN** message B replies to A, C replies to B, and D is unrelated
- **THEN** `context(Query(thread=C.id))` returns A, B and C, and not D

#### Scenario: What a peer was asked is its own
- **WHEN** the user says "hi" in a room whose only answering peer is `bot`, so the say is asked of `bot` without being addressed to it
- **THEN** `context(Query(peer=bot))` includes the say

### Requirement: SELF is whoever asks
`SELF` SHALL be a peer value that `context()` resolves to the id of the peer asking, so a peer can write a query before it knows its own id. Applying a query that names `SELF` with nobody asking MUST raise `ValueError`, rather than silently match nothing.

#### Scenario: What passed between me and anyone
- **WHEN** the connector at id 2 asks `context(Query(peer=SELF))`, after the user asked it one question it answered and asked peer 3 another
- **THEN** it gets its own question and answer, and not the exchange with peer 3

#### Scenario: Nobody asking
- **WHEN** `Query(peer=SELF)` is applied without saying who asks
- **THEN** it raises `ValueError`

### Requirement: context() takes a Query
The `context` grant SHALL accept an optional `Query` as its first argument. It MUST apply the query's filters before `since`, `start` and `limit` given as keywords. Called with no query, it MUST behave exactly as before.

#### Scenario: Unchanged without a query
- **WHEN** a peer calls `context(limit=5)`
- **THEN** it gets the five newest messages, as it did before `Query` existed

### Requirement: The archive keeps who a message was asked of
The database backend SHALL keep each message's `asked_of` and give it back when it loads the message.

#### Scenario: Asked, closed and reopened
- **WHEN** the user says "hi" asked of `bot`, and the chat is closed and reopened on the same database
- **THEN** the reloaded say has `asked_of` set to `bot`, and `context(Query(peer=bot))` includes it

### Requirement: forget drops from the conversation too
`ChatSession.forget(before)` SHALL drop the messages stamped before `before` from the session's conversation, and every message when `before` is None, whether or not a backend declares `HookForget`; afterwards `context()` MUST NOT return them. It SHALL also ask the backend that declares `HookForget` to drop them from the archive, and MUST return the number the backend reports, or 0 when there is no such backend.

#### Scenario: Forgotten here, not only in the archive
- **WHEN** a session with the database backend holds three messages, and `forget(before=t)` is called with `t` after the first two
- **THEN** `context()` returns only the third, and `forget` returns 2

#### Scenario: Without a backend
- **WHEN** a session without a backend holds two messages and `forget()` is called
- **THEN** `context()` returns nothing, and `forget` returns 0
