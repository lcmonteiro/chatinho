# Tasks

## 1. Concurrent delivery in the session

- [x] 1.1 Replace `_queues`, `_drain` and the per-peer drain tasks with one tracked task per (peer, message), started from `_post`. Exceptions are logged and do not stop other deliveries. Verify: new test "a peer answers two questions at once" (two 0.3 s asks to one peer finish in < 0.45 s) and the existing `test_a_slow_peer_holds_up_only_itself` pass.
- [x] 1.2 Hold deliveries for peers not yet started, and flush them in order when `start()` starts each peer, including a peer added after start. Verify: "said before start" test, plus the existing session and frontend tests that say before `start()`.
- [x] 1.3 Make `close()` stop new deliveries, wait up to 5 s for the in-flight set, warn and cancel the rest, then fail every pending ask with `RuntimeError("the chat closed")`. Verify: tests "close lets a listener finish" and "close does not hang" (an `answer` that never returns; `close()` returns in about 5 s and the waiting ask raises).
- [x] 1.4 Add a test that a listener slower with the first of two messages still leaves `context()` in the order they were said.

## 2. Recursion and the depth limit

- [x] 2.1 Add `ChatSession(max_depth=8)`, the `_ANSWERING` ContextVar and the `_depth` map. Set the depth for an ask, `say(to=...)` and a `say` routed to the only answerer; set the var in each delivery task (the question's depth for `answer`, 0 for `listen`); drop entries when delivery ends. Verify: "unrelated questions are not nested" test (two user asks both have depth 1).
- [x] 2.2 Past the limit, skip `answer` and post an `ERROR` reply "too many nested asks (limit N)" as the peer's answer. Verify: tests "a loop stops at the limit" (two peers that always ask each other; the user still gets an answer) and "the limit is configurable" (`max_depth=2`, the third question's `answer` is not called).
- [x] 2.3 Add the recursion test: user -> A -> B -> A, with every question answered and nothing left in `_pending` after `close()`.

## 3. Frontend never waits

- [x] 3.1 In `ChatFrontend.on_command_input_submitted`, run `/command` in a Textual worker instead of awaiting it. Verify: a frontend test with a 1 s command; submitting returns in < 0.1 s, a following message is posted before the command's answer, and the answer appears afterwards.
- [x] 3.2 Add tests that a slow `@peer` ask does not delay the user's next message, and that a peer waiting on `ask(LOCAL, ...)` leaves the frontend sending and hearing.

## 4. Peers under concurrent calls

- [x] 4.1 Run all of `DatabaseBackend`'s database work on its own single-thread executor, created in `initialize` and shut down in `shutdown`. Verify: test saying 50 messages at once, then closing, reopening and loading all 50 in order (file and in-memory SQLite).
- [x] 4.2 Test `McpConnector` with three concurrent questions against an in-process server. If the shared FastMCP client is not reentrant across tasks, build one client per question. Verify: the three answers are correct and distinct.
- [x] 4.3 Test `OpenAIConnector` with three concurrent questions on the fake client: three distinct answers, one client built.

## 5. Tests and docs

- [x] 5.1 Rewrite the tests that wait with `asyncio.sleep(0.02)` for a queue (`tests/test_chat_session.py` around lines 147, 311, 445) to assert after `close()`, and reword the docstrings that mention queues. Verify: `pytest -q` passes.
- [x] 5.2 Update `CLAUDE.md` ("Nothing blocks", the layout line for `session.py`, "a peer: an id, a queue"), `README.md` (the four rules, the `close()` comment, the `connectors` comment) and `docs/SPEC.md` (rules 2-3, the `add_connector`/`close` table rows). Each states: a delivery is its own task, asks may recurse up to `max_depth`, connectors keep no conversation state, and a peer that needs order holds its own lock. Verify: `grep -rn "queue" CLAUDE.md README.md docs/SPEC.md src/chatinho` shows no stale claim.
- [x] 5.3 Run the CI checks: `ruff check src tests examples`, `mypy src/chatinho`, `pytest -q` and `openspec validate --all --strict --no-interactive`. All pass.
