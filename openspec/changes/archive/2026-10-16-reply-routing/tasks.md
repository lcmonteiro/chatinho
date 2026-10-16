# Tasks

## 1. An answer is never asked

- [x] 1.1 In `src/chatinho/session.py`, give `_post` a keyword `answer: bool = False` that keeps the message from being delivered to its `to` as a question (it still resolves a waiting `ask` and is heard by listeners), and pass `answer=True` from `_answered` and from the error reply in `_deliver`. Verify with new tests in `tests/test_message_delivery.py` for "An answer to an addressed say is heard, not answered" and "Two answering peers do not trade answers" (A's `answer` never called, two messages), and that "A peer that listens and answers asks another" still passes.
- [x] 1.2 Add a test for "A frontend that does not answer is not asked": a frontend that listens says `say(to=peer)`, and `caplog` holds no "was asked but does not declare" warning. Verify it fails before 1.1 and passes after, and that running `tests/test_mcp_frontend.py` with `-o log_cli=true -o log_cli_level=WARNING` shows no such warning.
- [x] 1.3 Replace `test_answers_traded_past_the_limit_are_dropped` with "Replies traded past the limit are dropped": two peers whose `answer` says a reply (`say(..., reply_to=msg.id)`) and returns None stop at the limit with no `ERROR` reply. Verify the new test passes and that the drop branch in `_deliver` is what stops it, by removing that branch and watching the test fail.

## 2. A reply goes back to whoever it replies to

- [x] 2.1 In `_say_for`, when `to` is None and the speaker is not `TOOL`, address a say with `reply_to` set to the replied message's author if that author is a peer other than the speaker and `LOCAL` and declares `HookAnswer`, and keep the lone-answerer rule for a say without `reply_to`. Fold both into one helper in place of `_only_answerer`. Verify with tests in `tests/test_answer_details.py` for "The user follows up on an answer", "Following up in a room with several peers", "Replying to a peer that does not answer", "Replying to a command's output", "An explicit recipient wins" and "Replying to oneself".
- [x] 2.2 Keep `test_a_reply_stays_a_broadcast` as the test of the narrowed scenario "A reply stays a reply" (a reply to the user's message stays a broadcast), updating its docstring if needed. Verify it passes unchanged.
- [x] 2.3 Add a mounted test in `tests/test_chat_frontend.py`: with one answering peer, select its answer, type a follow-up and submit through the input (not `send_pending_reply`); the peer's `answer` gets the follow-up. Verify it fails on the pre-change session and passes after.
- [x] 2.4 Update the routing rules in `docs/SPEC.md` (the routing table and "A room with one peer that answers is a conversation with it", plus a sentence on replies) and the routing table in CLAUDE.md. Verify `pytest tests/test_architecture.py` still passes and the text matches the delta specs.

## 3. Checks

- [x] 3.1 Run `ruff check src tests examples`, `mypy src/chatinho`, `pytest -q` and `openspec validate --all --strict --no-interactive`; all pass. Re-run the review's reproduction (a follow-up to the bot's answer is answered; one unprompted say between two answering peers makes one `answer` call) and confirm both.

## Workflow follow-up

- Archive the change with `/opsx:archive` after review, which folds the deltas into `openspec/specs/message-delivery` and `openspec/specs/answer-details`.
