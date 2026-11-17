# Refinement: strengthen-weak-tests

## Problem

The capability baselines and `fix-ask-failure-reply` left a list of acceptance criteria that claim more than their tests check (the criterion was reworded to fit the test, by choice, and the test noted as weak), and of behaviour that has no criterion or test at all. A regression in any of those places passes the suite unnoticed, so a `@ac` tag today does not always mean the behaviour is guarded. The baselines are all closed, so this is the moment to pay that debt down in one place.

## Outcomes

- Breaking any behaviour on the list below makes the suite fail.
- Every criterion on the list states what its test asserts, and no weaker than the behaviour the code has.
- No duplicate criteria and no dead code in the tests on the list.
- The library's behaviour is unchanged: no source file under `src/chatinho` changes except living docs written at close.

## Context

**Observed:**

| capability | gap | file |
|---|---|---|
| keys | AC-KEYS-003.2 says the error names the variable and the file; the test matches only `"MISSING in"` | `tests/keys/test_keys.py::test_a_dotenv_variable` |
| keys | AC-KEYS-006.1 parses `dotenv:conf/.env#KEY` and `dotenv:#KEY` but checks only `name`, never the path (`conf/.env`, default `.env`) | `tests/keys/test_keys.py::test_references` |
| connectors | AC-CONN-020.1 was reworded in its baseline to "the option is accepted, the connector answers and the agent has the task tool"; the test cannot tell a passed `subagents` option from the default (e.g. `researcher` named in the `task` tool's description) | `tests/connectors/test_deep_agent_connector.py::test_deep_agents_options_reach_the_agent` |
| frontends | REQ-FRONT-025 says a reply with status `error` yields a tool error; no test has the asked peer return `Reply(status="error")` | `tests/frontends/test_mcp_frontend.py` |
| frontends | AC-FRONT-025.5 and AC-FRONT-025.6 are the same scenario (the asked peer's `answer` raises) | `src/chatinho/frontends/docs/spec.md` |
| frontends | AC-FRONT-020.11 was reworded to "copying raises nothing and reports no helper"; that the failing helper is logged is untested | `tests/frontends/test_clipboard.py` |
| commands | `/test` (`TestCommand`) is named in the spec's intro but has no requirement and no test | `src/chatinho/commands/test.py` |
| commands | AC-CMD-003.2 checks the base is unchanged after a refused merge and drop, not that the dropped workspace still exists | `tests/commands/test_workspace_command.py::test_a_model_cannot_merge` |
| commands | `/ws diff` on a workspace with no changes answers "<name>'s workspace has no changes."; untested | `src/chatinho/commands/workspace.py:67` |
| routers | AC-ROUTE-005.1 checks only that the lone peer was asked once, not that the reply to the user was posted with `to` unset | `tests/routers/test_message_routing.py::test_a_reply_to_the_user_goes_to_nobody` |
| workspaces | three branches with no scenario: a `view` that is not a `WorkspaceView` subclass (`TypeError`), a repo path that is not a directory (`ValueError`), a detached HEAD as base (the sha is used) | `src/chatinho/workspaces/git.py:73,112,118-119` |
| framework | the AC-CORE-011.5 test keeps a dead `try/except RuntimeError: pass` around the ask, which no longer raises | `tests/framework/test_message_delivery.py::test_a_failed_ask_is_in_the_conversation` |

Living docs: each capability's `<path>/docs/spec.md`; the gaps were recorded in the archived `review.md`/`validation.md` of `baseline-connectors`, `baseline-frontends` and `fix-ask-failure-reply`, and found while baselining the others.

**Assumed:**

- The code already does what the stronger criteria say (e.g. `DotEnv` names the file, the refused drop leaves the worktree, the router posts the reply with `to=None`). Not verified by running; a test that fails proves otherwise.
- `deepagents` exposes enough of the built graph (the `task` tool's description) to tell a passed `subagents` option from the default.

## Constraints

- [hard] No behaviour change in the library. A strengthened test that fails because of a real bug is not fixed here: it becomes its own `fix-<name>` change, as during the baselines.
- [hard] Never renumber or reuse an ID: AC-FRONT-025.6 is removed, and its ID retired.
- [hard] Tests stay under `tests/<capability>/` with `# @ac` tags; any new criterion goes in a MODIFIED requirement of its capability.
- [soft] Strengthen the existing test rather than add a parallel one, where the criterion already has a test.
- [soft] Keep the fake-based style: no network, real git repos for workspaces.

## Options

### Option A: one cross-cutting change with every gap

One change modifies the requirements of the seven capabilities: weak criteria get their stronger wording back and their tests strengthened; missing behaviour gets a criterion and a test; the duplicate is removed; the dead code goes.

- **Pros:** one review and one validate for work of a single shape; the whole list is closed at once.
- **Cons:** a wider diff to review, across seven capabilities.
- **Effort:** M
- **Touches:** keys, connectors, frontends, commands, routers, workspaces, framework
- **Outcomes:** meets all.

### Option B: one change per capability

Seven small changes, each refine → done.

- **Pros:** each review is small and local.
- **Cons:** seven full cycles for repetitive work.
- **Effort:** L
- **Touches:** same, one at a time
- **Outcomes:** meets all, slowly.

### Option C: only the highest-value gaps

The MCP `error` reply, the three workspaces refusals, `/test` and the dead code.

- **Pros:** fastest.
- **Cons:** leaves the weak keys, commands, routers and connectors tests as they are.
- **Effort:** S
- **Touches:** frontends, workspaces, commands, framework
- **Outcomes:** meets the outcomes only partly.

## Recommendation

Option A, chosen by the user: every gap is test and spec work of the same shape, so one cycle covers it.

## Open Questions

- If `deepagents` exposes nothing that tells a passed `subagents` option from the default, does AC-CONN-020.1 keep its current wording? (who can answer: the user, during specify or test)

## Candidate Capabilities

- `keys`: modified - AC-KEYS-003.2 and AC-KEYS-006.1 checked in full
- `connectors`: modified - AC-CONN-020.1 tells the passed option from the default
- `frontends`: modified - a peer's `error` reply over MCP, the failing clipboard helper's log, the duplicate AC-FRONT-025.6 removed
- `commands`: modified - `/test` gets a requirement, a refused drop keeps the workspace, `/ws diff` with no changes
- `routers`: modified - AC-ROUTE-005.1 checks the reply is addressed to nobody
- `workspaces`: modified - the three provider refusals and fallbacks
- `framework`: modified - the AC-CORE-011.5 test loses its dead code (no requirement change)
