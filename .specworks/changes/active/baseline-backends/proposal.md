# Proposal: baseline-backends

## Why

`backends` has no living spec: what `DatabaseBackend` promises is spread over the OpenSpec specs of message ids, attachments, context and delivery, and the tests. Recording the existing behaviour lets later changes MODIFY its requirements instead of only adding them.

## What Changes

- No behaviour change. The existing behaviour of `backends` is recorded as 8 requirements, and its existing tests and code gain `@ac` and `@req` tags.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `backends`: gains its first requirements, REQ-BACK-001 to REQ-BACK-008, all ADDED.

## Related requirements

REQ-CORE-019, REQ-CORE-020, REQ-CORE-023 and REQ-CORE-024 left: they say what the session asks of a backend (`load`, `forget`, `keep`, `link`); this change records what `DatabaseBackend` answers.

## Impact

Comment tags in `src/chatinho/backends/database.py` and `tests/backends/test_database_backend.py`. No API, data or dependency changes.

## Out of Scope

- No suspected bug was found in the behaviour read.
