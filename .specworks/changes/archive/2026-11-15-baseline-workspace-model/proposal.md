# Proposal: baseline-workspace-model

## Why

`workspace-model` has no living spec: what a workspace's operations promise is in one OpenSpec spec and the tests. Recording the existing behaviour lets later changes MODIFY its requirements instead of only adding them.

## What Changes

- No behaviour change. The existing behaviour of `workspace-model` is recorded as 10 requirements, and its existing tests and code gain `@ac` and `@req` tags.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `workspace-model`: gains its first requirements, REQ-WSM-001 to REQ-WSM-010, all ADDED.

## Related requirements

REQ-CORE-027 left: it says who is granted a workspace or a view; this change records what each can do with it.

## Impact

Comment tags in `src/chatinho/support/parts/workspace/operations.py`, `tree.py` and `views.py`, and in `tests/workspace-model/`. No API, data or dependency changes.

## Out of Scope

- What the provider refuses when it is given its own view and workspace classes (a workspace class that does not subclass the view, a view with a writing operation), and where worktrees and branches live: recorded by the baseline of `workspaces`.
- The agent tools and `/ws` built from `operations_of`: recorded by the baselines of `agents` and `commands`.
- No suspected bug was found in the behaviour read.
