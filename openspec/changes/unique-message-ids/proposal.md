# Proposal

## Why

`MessageStore` numbers messages `msg-1`, `msg-2`, … starting from 1 in every session. A chat that reopens on the same archive therefore hands out ids that already exist there: `DatabaseBackend` merges messages by id, so a new `msg-1` silently overwrites the archived `msg-1`, and anything keyed by message id — replies, and attachments once the backend keeps them — ends up pointing at the wrong message.

## What Changes

- Message ids become globally unique: `msg-` followed by 16 random hexadecimal characters (64 bits), for example `msg-3f9a1c2e7b04d5a6`. Uniqueness no longer depends on the session, the archive, or how much of it `start()` recalls.
- **BREAKING**: a message id is a `MessageID` object, not a string. `ChatMessage.id` and `reply_to`, what `say` returns, and what `locate`, `keep` and `link` take are all `MessageID`. `str()` gives `msg-` + hex, `MessageID.parse` reads it back, and `MessageID.new()` makes a fresh one; `MessageStore.new_id()` returns one.
- Like git's full and short commit hashes, the terminal shows a **short id**: the first 7 hexadecimal characters of the full id (`3f9a1c2` for `msg-3f9a1c2e7b04d5a6`). It is `MessageID.short`, and appears in the message header, the reply quote, the "Copied …" notice and the "Reply to …" placeholder. Everything else — replies, archives, attachments, `say`/`ask` return values — keeps using the full id. Ids from older archives (`msg-1`, …) are shown whole.
- **BREAKING**: code or tests that expect generated ids to be `msg-1`, `msg-2`, … must use the id `say` returns, or the message's `id`, instead; an id written by hand is `MessageID.parse("msg-1")`.
- Out of scope: renumbering or repairing ids already stored in existing archives, and accepting short ids as input (the terminal never asks the user to type an id).

## Capabilities

### New Capabilities
- `message-ids`: how the session assigns message ids, that they stay unique across sessions that share an archive, and the short form the terminal shows.

### Modified Capabilities
<!-- None. -->

## Impact

- `src/chatinho/chat_message.py`: the `MessageID` class, `MessageStore.new_id()`, and `ChatMessage.id`/`reply_to` typed as `MessageID`. `MessageID` is exported from `chatinho`.
- `src/chatinho/chat_hooks.py`, `src/chatinho/chat_session.py`: `say`, `locate` and the pending-ask map use `MessageID`.
- `src/chatinho/backends/database.py`: stores `str(id)` and parses it back on `load`; `keep`/`link` take a `MessageID`.
- `src/chatinho/chat_log.py`, `src/chatinho/chat_app.py`: show `.short` in the header, reply quote, copy notice and reply placeholder; widget maps and the reply target hold `MessageID`s.
- Tests that build ids by hand use `MessageID.parse`; new tests for `MessageID` and for what the terminal shows.
- `docs/SPEC.md`: the `say`, `keep`, `link` and `locate` signatures, and a note on `MessageID`.
- `tests/test_database_backend.py`: a test that a reopened chat does not overwrite archived messages.
- `CLAUDE.md`: the two examples that show `msg-3`.
