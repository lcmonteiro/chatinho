# Proposal: baseline-framework

## Why

`framework` has no living spec: what the session, the hooks, the messages and the context promise is spread over eight OpenSpec specs, `docs/SPEC.md` and the tests. Recording the existing behaviour lets later changes MODIFY its requirements instead of only adding them.

## What Changes

- No behaviour change. The existing behaviour of `framework` is recorded as 29 requirements, and its existing tests and code gain `@ac` and `@req` tags.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `framework`: gains its first requirements, REQ-CORE-001 to REQ-CORE-029, all ADDED.

## Related requirements

None: no capability has a living spec yet.

## Impact

Comment tags in `src/chatinho/session.py`, `hooks.py`, `message.py`, `query.py`, `builder.py` and `__init__.py`, and in `tests/framework/`, `tests/test_package_layout.py` and `tests/test_architecture.py`. No API, data or dependency changes.

## Out of Scope

- Who answers a say that names nobody: the session hands it to the router, and what the router decides is recorded by the baseline of `routers`.
- What the OpenSpec specs absorbed here say about the terminal (welcome and notices, `@name`, short ids, opening links), the database backend (archiving ids, status and attachments) and MCP (declaring and delegating credentials): each is recorded by the baseline of `frontends`, `backends` or `connectors`.
- The layer rules `tests/test_architecture.py` enforces: they constrain the code's structure, not its behaviour, and stay in `docs/architecture.md`.
- Two statements in `openspec/specs/message-attachments` that the code no longer follows and later specs replaced: that `answer` may return a plain string, and that `ask` returns text. The baseline records what the code does (REQ-CORE-011, REQ-CORE-007).
- No suspected bug was found in the behaviour read.
