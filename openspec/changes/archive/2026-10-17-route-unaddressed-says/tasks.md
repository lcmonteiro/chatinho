# Tasks

## 1. An answer is addressed to nobody

- [x] 1.1 Write failing tests in `tests/test_message_delivery.py`: an `ask`'s answer has `to` unset; a late `say(reply_to=question)` from the asked peer has `to` unset and is not put to the asker's `answer`, even when the asker answers; the user's reply to a question put to them has `to` unset and resolves the `ask`. Verify they fail on the current code.
- [x] 1.2 In `session.py`, post `_answered`, the `error` reply and the depth error with `to=None`. In `_say_for`, treat a say whose `reply_to` names a message with `to == frm` as an answer (no routing, `to` stays None). Verify the tests from 1.1 pass.
- [x] 1.3 Resolve a waiting `ask` with `question.to == msg.frm`. Keep `asked_of` written, and the `_post` audience built from it, until 2.4 writes the routed peer into `to`, so the remaining readers still work. Verify `pytest -q tests/test_message_delivery.py tests/test_answer_details.py` passes, updating only the assertions on an answer's `to`.

## 2. The router

- [x] 2.1 Add `HookRoute` to `hooks.py` (demands `route`), its section and table row in `docs/SPEC.md`, and the fifteen-hook wording in `CLAUDE.md`. Verify `pytest -q tests/test_architecture.py tests/test_require.py` passes.
- [x] 2.2 Add `chatinho/routers/` with `SimpleRouter` (`HookRoute`, `HookPeers`, `HookContext`): the reply rule, then the lone-answering-peer rule, excluding the speaker and `LOCAL`. Export `HookRoute` and `SimpleRouter` from `__init__.py` and update the export count in `CLAUDE.md`. Verify `tests/test_package_layout.py` and the stdlib-only import check in `tests/test_architecture.py` pass.
- [x] 2.3 Make the router whoever declares `HookRoute`: `add_connector` records it and refuses a second with `ValueError`; `ChatSession(router=…)` registers it as `backend=` does and raises `TypeError` without `HookRoute`; with none, the session builds an unregistered `SimpleRouter` granted as `TOOL`. Thread `router=` through `build_chat_session` and `build_mcp_session`. Verify with new tests in `tests/test_message_routing.py` covering every scenario of "The router is whoever declares HookRoute".
- [x] 2.4 Replace `_answerer_of` in `_say_for` with the router call and its check (a peer other than the speaker that declares `HookAnswer`, otherwise None with a warning; an exception is logged and gives None). The routed id goes into `to`, before `_kept`/`_post`, and the `_post` audience is built from `msg.to`. Verify with tests in `tests/test_message_routing.py` covering every scenario of "A router decides who an unaddressed say is for", "What a router returns is checked" and "The default router".

## 3. Remove `asked_of` and `is_broadcast`

- [x] 3.1 Switch the readers: `Query(peer=)` drops the `asked_of` match, `McpFrontend.listen` compares with `question.to`, `AgentConnector.listen` checks `msg.to is None and msg.is_local`, and the echo in `examples/hooks.py` checks `msg.to is not None`. Update their docstrings. Verify `pytest -q tests/test_context_query.py tests/test_mcp_frontend.py tests/test_mcp_end_to_end.py tests/test_agent_connector.py tests/test_examples.py` passes.
- [x] 3.2 Remove `ChatMessage.asked_of` and `is_broadcast` (field, property, docstrings, module docstring table), and the `asked_of` column and mapping in `DatabaseBackend`. Verify with a test that a database file created with the old schema (`asked_of` column present) still loads and saves. Verify `grep -rn "asked_of\|is_broadcast" src examples tests` finds nothing.
- [x] 3.3 Move the routing tests in `tests/test_answer_details.py` that asserted `asked_of`/broadcast into `tests/test_message_routing.py`, asserting `to`. Verify `pytest -q` passes.

## 4. The terminal and the docs

- [x] 4.1 Send plain text from `ChatFrontend.on_command_input_submitted` in a worker, as commands are sent. Verify with a mounted test in `tests/test_chat_frontend.py`: a router sleeping one second, the input cleared and typeable before it returns, and the say in the log afterwards.
- [x] 4.2 Rewrite the routing parts of `CLAUDE.md` ("`to` is what the speaker chose; `asked_of`…", "Two ways to be told" on `is_broadcast`, the message table, Public API, Layout) and `docs/SPEC.md` (the message table, `HookListen`'s `is_broadcast` advice, the lone-answerer text). Add a router to `examples/hooks.py`. Verify `pytest -q tests/test_architecture.py tests/test_examples.py` and `grep -n "asked_of\|is_broadcast" CLAUDE.md docs/SPEC.md` finds only the history that explains the change.

## 5. Integration

- [x] 5.1 Run `ruff check src tests examples`, `mypy src/chatinho examples`, `pytest -q` and `openspec validate --all --strict --no-interactive`, and verify all four pass.

## 6. Review

- [x] 6.1 Make the router what `router=` is given and not a peer: `self.router`, granted as `TOOL`, `initialize`/`shutdown` with the rest; drop the `HookRoute` handling in `add_connector` and the session's own default. Verify with `tests/test_message_routing.py` covering every scenario of "The router is what router= is given".
- [x] 6.2 Give `SimpleRouter` from the builders when no `router=` is passed, and from `conftest.driven` and the hand-built sessions in the tests that stand in for a builder. Verify with the scenario "The builders' router" and `pytest -q`.
- [x] 6.3 Store `MessageID` columns through a `TypeDecorator`, so `DatabaseBackend` neither casts with `str()` nor tests for None, and let `MessageID.parse(None)` return None. Verify with `tests/test_message_store.py` and `tests/test_database_backend.py`.
