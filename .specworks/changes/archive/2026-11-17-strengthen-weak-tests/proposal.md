# Proposal: strengthen-weak-tests

## Why

The baselines and `fix-ask-failure-reply` left criteria reworded down to what a weak test checked, a duplicate criterion, and behaviour with no criterion or test at all, so breaking any of it passes the suite. This change pays that list down in one cycle (option A of the refinement), with no change to the library's behaviour.

## What Changes

- **keys**: AC-KEYS-003.2's test checks the error names the variable *and* the file; AC-KEYS-006.1 also checks each `dotenv` reference's path (`conf/.env`, and `.env` when none is given).
- **connectors**: AC-CONN-020.1 gets back what its title says: a `subagents` option reaches the agent, shown by the model calling `task` for the `researcher` subagent and that subagent running with its own system prompt, which the default agent has no subagent for.
- **frontends**: a new criterion for an asked peer that replies with status `error` over MCP (a tool error carrying the reply's text); AC-FRONT-025.6 is removed as a duplicate of AC-FRONT-025.5, its test folded into 025.5's; AC-FRONT-020.11 again says the failing helper is logged, and its test checks the log.
- **commands**: `/test` gets a requirement and tests; AC-CMD-003.2 also checks that a refused drop leaves the workspace in place; `/ws diff` on a workspace with no changes gets a criterion.
- **routers**: AC-ROUTE-005.1 also checks that the reply to the user is posted addressed to nobody.
- **workspaces**: criteria for a view class that is not a `WorkspaceView` (`TypeError`), a repository path that is not a directory (`ValueError`), and a detached HEAD, whose commit becomes the base.
- **framework**: the AC-CORE-011.5 test loses its dead `try/except RuntimeError: pass`. No requirement changes.

## Capabilities

### New Capabilities

- None

### Modified Capabilities

- `keys`: REQ-KEYS-003 (AC-KEYS-003.2 tested in full), REQ-KEYS-006 (AC-KEYS-006.1 names the paths)
- `connectors`: REQ-CONN-020 (AC-CONN-020.1 says the option reaches the agent)
- `frontends`: REQ-FRONT-020 (AC-FRONT-020.11 says the failure is logged), REQ-FRONT-025 (AC-FRONT-025.6 removed, AC-FRONT-025.9 added for a reply with status `error`)
- `commands`: REQ-CMD-002 (AC-CMD-002.3 no changes), REQ-CMD-003 (AC-CMD-003.2 the workspace survives), REQ-CMD-006 added (`/test`)
- `routers`: REQ-ROUTE-005 (AC-ROUTE-005.1 the reply is addressed to nobody)
- `workspaces`: REQ-WS-001 (AC-WS-001.4 a view class that is no `WorkspaceView`), REQ-WS-002 (AC-WS-002.5 not a directory, AC-WS-002.6 a detached HEAD)

## Related requirements

- REQ-CONN-020 modified
- REQ-FRONT-020 modified
- REQ-WSM-009 left: committing a workspace, matched on "no changes"; `/ws diff` reads the diff and commits nothing
- REQ-CONN-011 left: the basic connector's parameters; only the deep connector's `subagents` is in scope
- REQ-CORE-011 left: AC-CORE-011.5 already says what its test checks; only dead code in the test goes

## Impact

- Tests only: `tests/keys/test_keys.py`, `tests/connectors/test_deep_agent_connector.py`, `tests/frontends/test_mcp_frontend.py`, `tests/frontends/test_clipboard.py`, `tests/commands/test_workspace_command.py` and a new test file for `/test` under `tests/commands/`, `tests/routers/test_message_routing.py`, `tests/workspaces/test_git_worktrees.py`, `tests/framework/test_message_delivery.py`.
- `@req` tags may be added to `src/chatinho/commands/test.py` (REQ-CMD-006), which has none; no code behaviour changes.
- Living specs of the seven capabilities, at close.

## Out of Scope

- Any change in library behaviour. Assumption: the code already does what each strengthened criterion says; a strengthened test that fails on a real bug is not fixed here but becomes its own `fix-<name>` change, as in the baselines.
- `/help`'s own behaviour beyond what REQ-CMD-005 already says.
- Weak tests not on the refinement's list.
