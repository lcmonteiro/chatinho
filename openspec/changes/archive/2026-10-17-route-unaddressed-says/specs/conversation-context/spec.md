## MODIFIED Requirements

### Requirement: A Query says which messages
chatinho SHALL provide `Query`, an immutable value with these fields, all optional and combined with AND:
- `peer`: the messages from that peer, addressed to it, or replying to one of its messages;
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
- **WHEN** the user says "hi" in a room whose only answering peer is `bot`, so the router addresses the say to `bot`
- **THEN** `context(Query(peer=bot))` includes the say

#### Scenario: An answer to a peer is its own
- **WHEN** `bot` asks `sol`, and `sol` answers with `to` unset
- **THEN** `context(Query(peer=bot))` includes the answer, because it replies to `bot`'s question

## REMOVED Requirements

### Requirement: The archive keeps who a message was asked of
**Reason**: `asked_of` is removed. The archive already keeps `to`, and `to` now holds the routed peer.
**Migration**: None needed for new archives. An archive written before this change keeps an `asked_of` column that is no longer read.
