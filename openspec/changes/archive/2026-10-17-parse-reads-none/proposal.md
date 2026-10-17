# Proposal

## Why

`route-unaddressed-says` was changed in review so that `DatabaseBackend` stops wrapping every id it reads in `None if … else MessageID.parse(…)`. To make that possible, `MessageID.parse(None)` now returns `None`, so a field that may hold no id (`reply_to`) is read the same way as one that always holds one. That change shipped in code and tests, but the `message-ids` capability still says `parse` takes text and raises for anything else. This change writes the shipped behavior into the spec.

## What Changes

- `MessageID.parse(None)` returns `None`. Any other input that is not `msg-` followed by lowercase hexadecimal characters still raises `ValueError`.
- No code change: the behavior and its test (`tests/test_message_store.py::test_parse_reads_none_back_as_none`) already exist.

## Capabilities

### New Capabilities

### Modified Capabilities
- `message-ids`: "Message ids are MessageID objects" says what `MessageID.parse` does with `None`.

## Impact

- **Specs:** `openspec/specs/message-ids/spec.md`.
- **Code, tests, dependencies:** none. Already in `src/chatinho/message.py` (an `@overload` keeps `parse(str) -> MessageID` for type checkers) and in `tests/test_message_store.py`.
