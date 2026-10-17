# Tasks

"The checks" means `ruff check src tests examples`, `mypy src/chatinho examples` and `pytest -q`, all from the repo root.

## 1. context takes only a Query

- [ ] 1.1 In `tests/test_context_query.py`, add `test_a_keyword_is_refused`: `context(limit=5)` raises `TypeError`. Rewrite `test_unchanged_without_a_query` so that `context()` returns all seven and `context(Query().last(5))` returns the five newest. Verify the new test **fails** on the current code.
- [ ] 1.2 In `tests/test_chat_session.py`, rewrite `test_context_narrows_by_index_and_by_time` as `test_context_narrows_by_time_and_count`, using `Query(limit=2)`, `Query(since=cut)` and `Query(limit=0)`, and drop the `start` case.
- [ ] 1.3 In `src/chatinho/session.py`, give `_context_for`'s grant and `_context` only `query` (and `asker`), and remove the `since`/`start`/`limit` filtering. Update the `_context` docstring and the class docstring's `context(since=, start=, limit=)` line. In `src/chatinho/hooks.py`, make `Context.__call__` take only `query`, and update `HookContext`'s comment. Verify 1.1 and 1.2 pass.
- [ ] 1.4 In `src/chatinho/frontends/chat/messages.py`, make `ChatLog` read `self._read_context(Query().last(self.max_displayed))`, importing `Query` from `chatinho.query`. Verify `tests/test_chat_frontend.py` passes.

## 2. Docs and integration

- [ ] 2.1 Update `docs/SPEC.md`'s HookContext section (signature, the `limit=50` example and the sentence about the keywords), CLAUDE.md's "Context has two tiers" paragraph, and `examples/hooks.py`'s comment to `context(query=None)`. Grep `src`, `examples`, `docs`, CLAUDE.md and the README for `since=, start=` and `context(limit` and leave none behind.
- [ ] 2.2 Run the checks and `openspec validate --all --strict --no-interactive`. All must pass.
