# Proposal: baseline-workspaces

## Why

`workspaces` has no living spec: what `GitWorktrees` promises is in the OpenSpec spec of peer workspaces, `CLAUDE.md` and the tests. Recording the existing behaviour lets later changes MODIFY its requirements instead of only adding them.

## What Changes

- No behaviour change. The existing behaviour of `workspaces` is recorded as 5 requirements, and its existing tests and code gain `@ac` and `@req` tags.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `workspaces`: gains its first requirements, REQ-WS-001 to REQ-WS-005, all ADDED.

## Related requirements

REQ-CORE-026 and REQ-CORE-027 left: they say how the session holds a provider and grants workspaces; this change records what `GitWorktrees` does when it is asked. REQ-WSM-001 to REQ-WSM-010 left: what a workspace can do once made. REQ-CMD-003 left: `/ws merge` and `/ws drop` call the provider's `merge` and `drop`.

## Impact

Comment tags in `src/chatinho/workspaces/git.py` and `tests/workspaces/test_git_worktrees.py`. No API, data or dependency changes.

## Out of Scope

- No suspected bug was found in the behaviour read.
