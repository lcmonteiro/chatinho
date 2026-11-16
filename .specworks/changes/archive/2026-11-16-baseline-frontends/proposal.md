# Proposal: baseline-frontends

## Why

`frontends` has no living spec: what the terminal and the MCP server promise is in one OpenSpec spec, parts of five others, `CLAUDE.md` and the tests. Recording the existing behaviour lets later changes MODIFY its requirements instead of only adding them.

## What Changes

- No behaviour change. The existing behaviour of `frontends` is recorded as 28 requirements, and its existing tests and code gain `@ac` and `@req` tags.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `frontends`: gains its first requirements, REQ-FRONT-001 to REQ-FRONT-028, all ADDED.

## Related requirements

REQ-CORE-003 left: it makes the frontend peer zero; this change records what each frontend does there. REQ-CORE-025 left: a credential rides on the message as it says. REQ-CONN-010 left: it is the lending side of what REQ-FRONT-028 receives. REQ-CORE-029 left: the builders that make each frontend.

## Impact

Comment tags in `src/chatinho/frontends/mcp.py` and `src/chatinho/frontends/chat/` (`__init__.py`, `messages.py`, `composer.py`, `clipboard.py`, `style.py`), and in `tests/frontends/`. No API, data or dependency changes.

## Out of Scope

- The exact colours of the default palette: the tests fix how the palette is used, not its values.
- No suspected bug was found in the behaviour read.
