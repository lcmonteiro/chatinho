# Tasks

## 1. asked_of decides who is asked

- [ ] 1.1 Add `asked_of: Optional[int] = None` to `ChatMessage` in `src/chatinho/message.py`, documented beside `to`. Verify `tests/test_message_store.py` still passes.
- [ ] 1.2 In `src/chatinho/session.py`: `_ask_for` sets `asked_of = to`; `_say_for` sets `asked_of = to` when `to` is given, else `self._answerer_of(frm, reply_to)` for a non-`TOOL` speaker, and never writes `msg.to`; `_post` builds its audience from `asked_of` (keeping the `resolved` check), and the `answer` keyword and its two callers' `answer=True` go. Verify the existing delivery tests (`test_message_delivery.py`, `test_answer_details.py`) pass, which shows answers are still never asked without the flag.
- [ ] 1.3 Update the tests that used `to`/`is_broadcast` to mean "asked of": `test_answer_details.py:100` asserts `said.to is None and said.asked_of == eco.peer_id`; the asserts at `:133`, `:143`, `:259`, `:272`, `:297` assert `asked_of is None` (each keeps `is_broadcast` where it still holds). Add tests for "Routed, and still said to the room" (an echo-style listener next to one answering peer hears the user's say, and the peer answers once), and for "Asked directly", "An answer is asked of nobody" and "A command is asked of nobody". Verify that "Routed, and still said to the room" fails on the code before 1.2.

## 2. The agent answers once

- [ ] 2.1 In `src/chatinho/connectors/agent.py`, `listen` returns early when `msg.asked_of == self.peer_id`. Add a test in `tests/test_agent_connector.py` for "The only answering peer": with the agent as the lone answering peer, the user's say runs the model once and produces one reply and no say. Verify it fails without the guard (two runs).

## 3. Memory finds what a peer was asked

- [ ] 3.1 In `src/chatinho/query.py`, the `peer` filter also matches `m.asked_of == peer`; update the `Query.peer` docstring. Add a test in `tests/test_context_query.py` for "What a peer was asked is its own". Verify it fails without the new clause.
- [ ] 3.2 In `src/chatinho/backends/database.py`: add the `asked_of` column, write it in `_write`, read it in `_read`, and in `initialize()` add the column with `ALTER TABLE messages ADD COLUMN asked_of INTEGER` when the inspected `messages` table lacks it. Add tests in `tests/test_database_backend.py` for "Asked, closed and reopened" and "An older database" (create the old table by hand in a temp SQLite file, insert one row, start the backend, load, archive a new message). Verify the older-database test fails without the `ALTER TABLE`.

## 4. Docs

- [ ] 4.1 Update `docs/SPEC.md` (the routing table: `to` is the speaker's, `asked_of` is the session's; the lone-answerer and reply paragraphs; the `HookListen` note on `is_broadcast`), CLAUDE.md's routing paragraph, and the `ChatMessage`/`message.py` module docstring. Verify `pytest tests/test_architecture.py` passes and the text matches the delta specs.

## 5. Checks

- [ ] 5.1 Run `ruff check src tests examples`, `mypy src/chatinho examples`, `pytest -q` and `openspec validate --all --strict --no-interactive`; all pass. Re-run the review's reproduction B (an echo listener beside one answering bot) and confirm the echo now fires and the bot answers once.

## Workflow follow-up

- Archive with `/opsx:archive` after review, which folds the deltas into `answer-details`, `conversation-context` and `agent-connector`.
