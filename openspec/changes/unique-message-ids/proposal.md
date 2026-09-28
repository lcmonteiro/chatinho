# Proposal

## Why

`MessageStore` numbers messages `msg-1`, `msg-2`, … starting from 1 in every session. A chat that reopens on the same archive therefore hands out ids that already exist there: `DatabaseBackend` merges messages by id, so a new `msg-1` silently overwrites the archived `msg-1`, and anything keyed by message id — replies, and attachments once the backend keeps them — ends up pointing at the wrong message.

## What Changes

- Message ids become globally unique: `msg-` followed by 16 random hexadecimal characters (64 bits), for example `msg-3f9a1c2e7b04d5a6`. Uniqueness no longer depends on the session, the archive, or how much of it `start()` recalls.
- `MessageStore.new_id()` keeps its signature and its thread safety; only the format changes.
- **BREAKING** (format only): code or tests that expect generated ids to be `msg-1`, `msg-2`, … must use the id `say`/`ask` return, or the message's `id`, instead. Ids passed in explicitly (for example `ChatMessage(id="msg-1", …)`) are unaffected.
- Out of scope: renumbering or repairing ids already stored in existing archives, and shortening how the terminal header displays the id.

## Capabilities

### New Capabilities
- `message-ids`: how the session assigns message ids, and that they stay unique across sessions that share an archive.

### Modified Capabilities
<!-- None. -->

## Impact

- `src/chatinho/chat_message.py`: `MessageStore.new_id()` and the `ChatMessage.id` docstring.
- `tests/test_message_store.py`, `tests/test_chat_app.py`: the two tests that assert the old counting format.
- `tests/test_database_backend.py`: a test that a reopened chat does not overwrite archived messages.
- `CLAUDE.md`: the two examples that show `msg-3`.
