# Proposal: baseline-routers

## Why

`routers` has no living spec: who answers a say that names nobody is in the OpenSpec spec of message routing, `CLAUDE.md` and the tests. Recording the existing behaviour lets later changes MODIFY its requirements instead of only adding them.

## What Changes

- No behaviour change. The existing behaviour of `routers` is recorded as 6 requirements, and its existing tests and code gain `@ac` and `@req` tags.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `routers`: gains its first requirements, REQ-ROUTE-001 to REQ-ROUTE-006, all ADDED.

## Related requirements

REQ-CORE-009 and REQ-CORE-012 left: they say what an addressed say and an answer are; this change records how a say with no `to` gets one. REQ-CORE-029 left: the builders, whose default router REQ-ROUTE-006 records.

## Impact

Comment tags in `src/chatinho/routers/simple.py`, in the code of `src/chatinho/session.py` that consults the router, in `src/chatinho/builder.py`, and in `tests/routers/test_message_routing.py`. No API, data or dependency changes.

## Out of Scope

- No suspected bug was found in the behaviour read.
