# Tasks

"The checks" means `ruff check src tests examples`, `mypy src/chatinho examples` and `pytest -q`, all from the repo root.

## 1. A Reply reads as what it says

- [x] 1.1 Add tests for `str(Reply)` in the test file that covers `Reply` (`tests/test_answer_details.py`): `Reply("sunny")` reads `sunny`, `status="asked"` reads `asked: which city?`, `status="error"` reads `error: quota exceeded`, and `repr` still names `text=`, `attachments=` and `status=`. Verify the first three **fail** on the current code.
- [x] 1.2 Give `Reply` in `src/chatinho/message.py` a `__str__` that returns the text when the status is `ANSWERED` and `"%s: %s" % (status.value, text)` otherwise, with a docstring line saying why (design Decisions 1–2). Verify 1.1 passes.

## 2. The model reads it

- [x] 2.1 In `tests/test_agent_connector.py`, add a test that reads the `ToolMessage` the fake model was sent after calling `ask_coder` (`model.sent`). Its content must be the coder's answer text alone, with no `Reply(` in it. Add a second case where the peer answers `Reply("quota exceeded", status="error")`: the content must be `error: quota exceeded`. Verify both **fail** without 1.2 and pass with it.
- [x] 2.2 Update the existing agent tests that compare with `str(Reply(...))` (`test_asking_another_peer`, `test_asked_back`) to the plain expected text. In `test_a_loop_of_agents_stops_at_max_depth`, look for `error: ` instead of `ReplyStatus.ERROR`. Leave `connectors/agent.py` unchanged. Verify the checks pass.

## 3. Docs and integration

- [x] 3.1 In `docs/SPEC.md`'s `ask` section, and in CLAUDE.md where "`ask` returns the answer's `Reply`", add one sentence saying how a `Reply` reads as text and that this is what an agent's `ask_<peer>` tool hands the model.
- [x] 3.2 Run the checks and `openspec validate --all --strict --no-interactive`. All must pass.
