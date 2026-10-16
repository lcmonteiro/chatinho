## MODIFIED Requirements

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

## ADDED Requirements

### Requirement: The archive keeps who a message was asked of
The database backend SHALL keep each message's `asked_of` and give it back when it loads the message.

#### Scenario: Asked, closed and reopened
- **WHEN** the user says "hi" asked of `bot`, and the chat is closed and reopened on the same database
- **THEN** the reloaded say has `asked_of` set to `bot`, and `context(Query(peer=bot))` includes it
