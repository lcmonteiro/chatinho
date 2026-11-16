# Tasks: strengthen-weak-tests

## 1. keys

- [ ] 1.1 [test] Strengthen `test_a_dotenv_variable` to assert the error names the variable and the file's path (AC-KEYS-003.2), and `test_references` to assert the dotenv sources' paths `conf/.env` and `.env` (AC-KEYS-006.1); verify with `uv run pytest -q tests/keys`
- [x] 1.2 [code] Confirm `src/chatinho/support/parts/keys/sources.py` stays tagged `@req REQ-KEYS-003` and `@req REQ-KEYS-006` with no behaviour change (REQ-KEYS-003, REQ-KEYS-006); verify with `git diff` showing no change there

## 2. connectors

- [ ] 2.1 [test] Rewrite `test_deep_agents_options_reach_the_agent` per design D1: the model calls `task` for `researcher`, the subagent runs with `Research.` and its answer reaches the connector's answer (AC-CONN-020.1); verify with `uv run pytest -q tests/connectors/test_deep_agent_connector.py`
- [x] 2.2 [code] Confirm `src/chatinho/connectors/agents/deep.py` stays tagged `@req REQ-CONN-020` with no behaviour change (REQ-CONN-020); verify with `git diff` showing no change there

## 3. frontends

- [ ] 3.1 [test] Add `caplog` to the AC-FRONT-020.11 test and assert a warning naming the helper (AC-FRONT-020.11); verify with `uv run pytest -q tests/frontends/test_clipboard.py`
- [ ] 3.2 [test] Delete `test_ask_a_peer_that_fails` and its AC-FRONT-025.6 tag (REMOVED criterion), and add a test where the asked peer returns `Reply("quota exceeded", status=error)` and the result is a tool error with that text (AC-FRONT-025.9); verify with `uv run pytest -q tests/frontends/test_mcp_frontend.py` and `grep -r AC-FRONT-025.6 tests` finding nothing
- [x] 3.3 [code] Confirm `src/chatinho/frontends/chat/clipboard.py` and `src/chatinho/frontends/mcp.py` stay tagged `@req REQ-FRONT-020` and `@req REQ-FRONT-025` with no behaviour change (REQ-FRONT-020, REQ-FRONT-025); verify with `git diff` showing no change there

## 4. commands

- [ ] 4.1 [test] Write `tests/commands/test_test_command.py` for `/test` per design D5 (AC-CMD-006.1, AC-CMD-006.2, AC-CMD-006.3); verify with `uv run pytest -q tests/commands`
- [ ] 4.2 [test] Add a test for `/ws diff` with no changes (AC-CMD-002.3), and strengthen `test_a_model_cannot_merge` to assert dev's workspace is still listed with its commit after the refused drop (AC-CMD-003.2); verify with `uv run pytest -q tests/commands`
- [x] 4.3 [code] Tag `TestCommand` in `src/chatinho/commands/test.py` with `@req REQ-CMD-006`, and confirm `src/chatinho/commands/workspace.py` stays tagged `@req REQ-CMD-002` and `@req REQ-CMD-003` with no behaviour change (REQ-CMD-006, REQ-CMD-002, REQ-CMD-003); verify with `specworks run lint` and `git diff` showing only the tag

## 5. routers

- [ ] 5.1 [test] Strengthen `test_a_reply_to_the_user_goes_to_nobody` to assert the peer's reply is posted with `to` unset (AC-ROUTE-005.1); verify with `uv run pytest -q tests/routers`
- [x] 5.2 [code] Confirm `src/chatinho/routers/simple.py` stays tagged `@req REQ-ROUTE-005` with no behaviour change (REQ-ROUTE-005); verify with `git diff` showing no change there

## 6. workspaces

- [ ] 6.1 [test] Add tests for a view class that is no `WorkspaceView` (AC-WS-001.4), a repository path that is a file or missing (AC-WS-002.5), and a detached HEAD whose sha becomes the base (AC-WS-002.6); verify with `uv run pytest -q tests/workspaces`
- [x] 6.2 [code] Confirm `src/chatinho/workspaces/git.py` stays tagged `@req REQ-WS-001` and `@req REQ-WS-002` with no behaviour change (REQ-WS-001, REQ-WS-002); verify with `git diff` showing no change there

## Workflow follow-up

- A strengthened test that fails on a real bug is not fixed in the code half: it is reported in review and becomes its own `fix-<name>` change.
- The dead `try/except RuntimeError: pass` in `tests/framework/test_message_delivery.py::test_a_failed_ask_is_in_the_conversation` (AC-CORE-011.5) goes with the test half's work, awaiting the ask directly (design D6). It is no task because the framework has no delta spec: no requirement changes, and a task may only name IDs this change specifies.
