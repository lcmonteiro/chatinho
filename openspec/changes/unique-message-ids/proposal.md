# Proposal

## Why

`MessageStore` numbers messages `msg-1`, `msg-2`, … starting from 1 in every session. A chat that reopens on the same archive therefore hands out ids that already exist there: `DatabaseBackend` merges messages by id, so a new `msg-1` silently overwrites the archived `msg-1`, and anything keyed by message id — replies, and attachments once the backend keeps them — ends up pointing at the wrong message.

## What Changes

- Message ids become globally unique: `msg-` followed by 16 random hexadecimal characters (64 bits), for example `msg-3f9a1c2e7b04d5a6`. Uniqueness no longer depends on the session, the archive, or how much of it `start()` recalls.
- `MessageStore.new_id()` keeps its signature and its thread safety; only the format changes.
- Like git's full and short commit hashes, the terminal shows a **short id**: the first 7 hexadecimal characters of the full id (`3f9a1c2` for `msg-3f9a1c2e7b04d5a6`). It appears in the message header, the reply quote, the "Copied …" notice and the "Reply to …" placeholder. Everything else — replies, archives, attachments, `say`/`ask` return values — keeps using the full id. Ids not in the new format (explicit ids, or ones in older archives) are shown as they are.
- **BREAKING** (format only): code or tests that expect generated ids to be `msg-1`, `msg-2`, … must use the id `say`/`ask` return, or the message's `id`, instead. Ids passed in explicitly (for example `ChatMessage(id="msg-1", …)`) are unaffected.
- Out of scope: renumbering or repairing ids already stored in existing archives, and accepting short ids as input (the terminal never asks the user to type an id).

## Capabilities

### New Capabilities
- `message-ids`: how the session assigns message ids, that they stay unique across sessions that share an archive, and the short form the terminal shows.

### Modified Capabilities
<!-- None. -->

## Impact

- `src/chatinho/chat_message.py`: `MessageStore.new_id()`, a `short_id()` helper, and the `ChatMessage.id` docstring.
- `src/chatinho/chat_log.py`, `src/chatinho/chat_app.py`: show `short_id(...)` in the header, reply quote, copy notice and reply placeholder.
- `tests/test_message_store.py`, `tests/test_chat_app.py`: the two tests that assert the old counting format, plus tests for `short_id` and for what the terminal shows.
- `tests/test_database_backend.py`: a test that a reopened chat does not overwrite archived messages.
- `CLAUDE.md`: the two examples that show `msg-3`.
