# Proposal: baseline-commands

## Why

`commands` has no living spec: what `/ws` promises is in `CLAUDE.md` and its tests. Recording the existing behaviour lets later changes MODIFY its requirements instead of only adding them.

## What Changes

- No behaviour change. The existing behaviour of `commands` is recorded as 5 requirements, and its existing tests and code gain `@ac` and `@req` tags.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `commands`: gains its first requirements, REQ-CMD-001 to REQ-CMD-005, all ADDED.

## Related requirements

REQ-CORE-013 left: how a command runs is the session's; this change records what `/ws` does when it runs. REQ-FRONT-004 left: the terminal's `/help` lists the commands and peers.

## Impact

Comment tags in `src/chatinho/commands/workspace.py` and `help.py`, and in `tests/commands/test_workspace_command.py`. No API, data or dependency changes.

## Out of Scope

- `/test` (`TestCommand`): no test covers it. Recording it would need a new test; it is left to a later change.
- What `/help` lists beyond `/ws`: REQ-FRONT-004 already records it from the terminal's tests.
- No suspected bug was found in the behaviour read.
