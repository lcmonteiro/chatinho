# Proposal

## Why

The `context` grant has two ways to say "since" and "how many": `context(Query(since=t, limit=20))` and `context(since=t, limit=20)`. Both appear in `docs/SPEC.md` side by side, and the grant's docstring has to explain the order they apply in. Its third keyword, `start`, is an index into a list that shifts whenever a message is posted or forgotten. Nothing in `src/` or `examples/` passes it; only one test does.

The keywords predate `Query` and were kept so that existing calls would not change. In practice, one library caller uses them: `ChatLog` reads `context(limit=max_displayed)`. Every other caller passes a `Query` or nothing.

## What Changes

- **BREAKING** `context` takes one optional argument, a `Query`. The keywords `since`, `start` and `limit` are removed. `since` and `limit` are `Query` fields already. `start` has no replacement, because an index into a changing list names no particular message.
- `ChatLog` reads `context(Query().last(max_displayed))`.
- The `Context` protocol, `HookContext`'s comment, the session's docstrings, `docs/SPEC.md`, CLAUDE.md and `examples/hooks.py` describe `context(query=None)`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `conversation-context`: "context() takes a Query" says `context` takes only a `Query`, and drops the keywords.

## Impact

- **Code:** `src/chatinho/session.py` (`_context_for`, `_context`), `src/chatinho/hooks.py` (`Context`, `HookContext`'s comment), `src/chatinho/frontends/chat/messages.py` (`ChatLog` passes a `Query`).
- **Tests:** `test_context_narrows_by_index_and_by_time` (`tests/test_chat_session.py`) and `test_unchanged_without_a_query` (`tests/test_context_query.py`) are rewritten to use `Query`. A new test shows the keywords are refused.
- **Docs:** `docs/SPEC.md` (HookContext), CLAUDE.md ("Context has two tiers"), `examples/hooks.py`'s comment.
- **API:** a peer that called `context(limit=…)`, `context(since=…)` or `context(start=…)` gets a `TypeError` and must pass a `Query`. The library is not on PyPI and is treated as its first version, so nothing is deprecated first.
