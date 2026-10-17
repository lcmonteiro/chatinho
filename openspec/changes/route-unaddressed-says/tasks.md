# Tasks

## 1. An answer is addressed to nobody

- [ ] 1.1 Write failing tests in `tests/test_message_delivery.py`: an `ask`'s answer has `to` unset; a late `say(reply_to=question)` from the asked peer has `to` unset and is not put to the asker's `answer`, even when the asker answers; the user's reply to a question put to them has `to` unset and resolves the `ask`. Verify they fail on the current code.
- [ ] 1.2 In `session.py`, post `_answered`, the `error` reply and the depth error with `to=None`. In `_say_for`, treat a say whose `reply_to` names a message with `to == frm` as an answer (no routing, `to` stays None). Verify the tests from 1.1 pass.
- [ ] 1.3 Resolve a waiting `ask` with `question.to == msg.frm`, and build the `_post` audience from `msg.to`. Keep `asked_of` written for now, so the remaining readers still work. Verify `pytest -q tests/test_message_delivery.py tests/test_answer_details.py` passes, updating only the assertions on an answer's `to`.

## 2. The router

- [ ] 2.1 Add `HookRoute` to `hooks.py` (demands `route`), its section and table row in `docs/SPEC.md`, and the fifteen-hook wording in `CLAUDE.md`. Verify `pytest -q tests/test_architecture.py tests/test_require.py` passes.
- [ ] 2.2 Add `chatinho/routers/` with `SimpleRouter` (`HookRoute`, `HookPeers`, `HookContext`): the reply rule, then the lone-answering-peer rule, excluding the speaker and `LOCAL`. Export `HookRoute` and `SimpleRouter` from `__init__.py` and update the export count in `CLAUDE.md`. Verify `tests/test_package_layout.py` and the stdlib-only import check in `tests/test_architecture.py` pass.
- [ ] 2.3 Add `ChatSession(router=…)`. It defaults to `SimpleRouter()`, raises `TypeError` without `HookRoute`, grants it as `TOOL`, and calls its `initialize`/`shutdown` with the commands'. Thread `router=` through `build_chat_session` and `build_mcp_session`. Verify with new tests in `tests/test_message_routing.py` for "A router is declared, and is not a peer".
- [ ] 2.4 Replace `_answerer_of` in `_say_for` with the router call and its check (a peer other than the speaker that declares `HookAnswer`, otherwise None with a warning; an exception is logged and gives None). The routed id goes into `to`, before `_kept`/`_post`. Verify with tests in `tests/test_message_routing.py` covering every scenario of "A router decides who an unaddressed say is for", "What a router returns is checked" and "The default router".

## 3. Remove `asked_of` and `is_broadcast`

- [ ] 3.1 Switch the readers: `Query(peer=)` drops the `asked_of` match, `McpFrontend.listen` compares with `question.to`, `AgentConnector.listen` checks `msg.to is None and msg.is_local`, and the echo in `examples/hooks.py` checks `msg.to is not None`. Update their docstrings. Verify `pytest -q tests/test_context_query.py tests/test_mcp_frontend.py tests/test_mcp_end_to_end.py tests/test_agent_connector.py tests/test_examples.py` passes.
- [ ] 3.2 Remove `ChatMessage.asked_of` and `is_broadcast` (field, property, docstrings, module docstring table), and the `asked_of` column and mapping in `DatabaseBackend`. Verify with a test that a database file created with the old schema (`asked_of` column present) still loads and saves. Verify `grep -rn "asked_of\|is_broadcast" src examples tests` finds nothing.
- [ ] 3.3 Move the routing tests in `tests/test_answer_details.py` that asserted `asked_of`/broadcast into `tests/test_message_routing.py`, asserting `to`. Verify `pytest -q` passes.

## 4. The terminal and the docs

- [ ] 4.1 Send plain text from `ChatFrontend.on_command_input_submitted` in a worker, as commands are sent. Verify with a mounted test in `tests/test_chat_frontend.py`: a router sleeping one second, the input cleared and typeable before it returns, and the say in the log afterwards.
- [ ] 4.2 Rewrite the routing parts of `CLAUDE.md` ("`to` is what the speaker chose; `asked_of`…", "Two ways to be told" on `is_broadcast`, the message table, Public API, Layout) and `docs/SPEC.md` (the message table, `HookListen`'s `is_broadcast` advice, the lone-answerer text). Add a router to `examples/hooks.py`. Verify `pytest -q tests/test_architecture.py tests/test_examples.py` and `grep -n "asked_of\|is_broadcast" CLAUDE.md docs/SPEC.md` finds only the history that explains the change.

## 5. Integration

- [ ] 5.1 Run `ruff check src tests examples`, `mypy src/chatinho examples`, `pytest -q` and `openspec validate --all --strict --no-interactive`, and verify all four pass.
