# Design: strengthen-weak-tests

## Context

The change is cross-cutting (six capabilities' specs, seven test folders) but changes no behaviour: see `proposal.md`. Every modified requirement except REQ-CMD-006 is already tagged `@req` in its code; the work is in the tests. This design records how each test proves its criterion, so the test half does not fall back to the weak checks it replaces.

## Goals / Non-Goals

**Goals:**
- Each strengthened test fails when the behaviour its criterion names is broken, not only when the code crashes.
- Tests stay where their capability's tests are, and an existing test is strengthened in place where the criterion already has one.

**Non-Goals:**
- No library code change beyond adding `@req REQ-CMD-006` to `src/chatinho/commands/test.py`.
- No new test doubles beyond what a test needs locally; `tests/fakes/` stays as it is.

## Decisions

### D1: AC-CONN-020.1 is proved by the subagent running, not by a tool description (REQ-CONN-020)

The fake model (`tests/fakes/agent.py`) records only the tool *names* it is bound to, so the `task` tool's description, which would name `researcher`, is not observable, and `task` is present with or without `subagents`. The test scripts the model as a function of what it is sent: when the system prompt is the subagent's `Research.`, it answers `found`; otherwise, the first time it calls `task` with `subagent_type="researcher"`, and once the tool result arrives, it answers with that result. The assertions: some request sent to the model carried the system prompt `Research.`, the tool result holds `found`, and the connector's answer does too. Without the option deep agents has no `researcher` and the tool result is an error, so the test fails.

- Alternative: inspect the built graph for the subagent. Rejected: it reads deepagents' internals, which move between versions.

### D2: The log is read with `caplog` (REQ-FRONT-020)

AC-FRONT-020.11's existing parametrised test gains `caplog` at `WARNING` for the `chatinho.frontends.chat.clipboard` logger, and asserts one record naming the helper (`termux-clipboard-set`).

### D3: The duplicate is folded, not deleted blind (REQ-FRONT-025)

`test_ask_a_peer_that_fails` (AC-FRONT-025.6, two peers, the `ask` tool by `call`) checks the same as `test_a_failing_peer_is_an_error` (AC-FRONT-025.5). The test half deletes the 025.6 test and its tag; 025.5's test keeps its own. AC-FRONT-025.9 is a new test whose peer returns `Reply("quota exceeded", status=ReplyStatus.ERROR)`, asserting the tool error's text is `quota exceeded`.

### D4: What each other strengthened test adds

| criterion | added assertion |
|---|---|
| AC-KEYS-003.2 | the message holds `MISSING` and the dotenv file's path |
| AC-KEYS-006.1 | the `path` of the two dotenv sources: `conf/.env` and `.env` (as `pathlib.Path`) |
| AC-CMD-003.2 | after the refused drop, `dev` is still listed by `/ws` with its 1 commit ahead |
| AC-CMD-002.3 | `/ws diff dev` on a fresh workspace answers `dev's workspace has no changes.` and the reply has no attachments |
| AC-ROUTE-005.1 | the reply posted by the second peer has `to is None` |
| AC-WS-001.4 | `GitWorktrees(repo, view=object)` raises `TypeError` matching `WorkspaceView` |
| AC-WS-002.5 | starting on a file and on a missing path raises `ValueError` matching `not a directory` |
| AC-WS-002.6 | after `git checkout --detach`, the provider's `base` is `git rev-parse HEAD` and a new workspace's branch starts there |

### D5: `/test` is tested through a session (REQ-CMD-006)

A new `tests/commands/test_test_command.py` drives `TestCommand` in a session built with `conftest.driven`, reading the conversation after `close()` for its three says (as `TOOL`) and the answer. The code half only adds the `@req REQ-CMD-006` tag.

### D6: The framework test loses its dead `try/except` (AC-CORE-011.5)

The ask in `test_a_failed_ask_is_in_the_conversation` no longer raises, so it is awaited directly. No requirement changes, so the framework has no delta spec.

## Interfaces

None: the API does not change.

## Diagrams

No structural change.

## Risks / Trade-offs

- A strengthened test may fail on a real bug → per the proposal, not fixed here; it becomes its own `fix-<name>` change and the criterion is settled in review.
- D1 depends on deepagents passing the subagent's `system_prompt` to the model as a system message → if it does not, the test half reports it and AC-CONN-020.1 is settled in review.

## Open Questions

None.
