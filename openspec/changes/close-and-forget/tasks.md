# Tasks

## 1. shutdown may be a coroutine

- [ ] 1.1 In `src/chatinho/session.py`, `close()` calls every `shutdown`, collects the awaitable results, and awaits them together with `asyncio.wait(..., timeout=self.CLOSE_TIMEOUT)`, logging each exception and warning about and cancelling each one still running. Add tests in `tests/test_chat_session.py` for the four `peer-lifecycle` scenarios ("An asynchronous shutdown is awaited", "A synchronous shutdown still works", "One failing shutdown does not stop the others", "A shutdown that never returns", the last with `CLOSE_TIMEOUT` patched low). Verify the first fails on the current `close()`.
- [ ] 1.2 Update CLAUDE.md's lifecycle table (`shutdown()` may be `async def`, awaited at `close`, bounded), SPEC.md's lifecycle paragraph, and the lifecycle comment in `src/chatinho/hooks.py`. Verify `pytest tests/test_architecture.py` passes.

## 2. The OpenAI connector closes its client

- [ ] 2.1 Add `async def shutdown` to `OpenAIConnector` that closes `self._client` when set and clears it. Add tests in `tests/test_openai_connector.py` for "Asked, then closed" (the `FakeOpenAI` built for its own key has `closed` set after `session.close()`) and "Never asked". Verify the first fails without `shutdown`.

## 3. forget drops from the conversation too

- [ ] 3.1 Add `MessageStore.forget(before)` in `src/chatinho/message.py`: keep the messages stamped at or after `before` (none when `before` is None), rebuild `_index` and `_replies`, return how many were dropped. Add tests in `tests/test_message_store.py`: messages, `find` and `replies` all forget, and a kept reply keeps its `reply_to`.
- [ ] 3.2 `ChatSession.forget` calls the store's `forget` first, then the backend's, and returns the backend's count or 0. Rewrite `test_forget_without_a_backend_drops_nothing` as "Without a backend" (returns 0, and `context()` is empty), and add "Forgotten here, not only in the archive" with the database backend in `tests/test_database_backend.py`. Update the `forget` docstring and SPEC.md's `HookForget` section. Verify both tests fail on the current `forget`.

## 4. Nothing blocks

- [ ] 4.1 In `src/chatinho/frontends/mcp.py`, `_attachments_of` reads each link with `await asyncio.to_thread(_read_link, url)`. Verify the MCP attachment tests (`tests/test_mcp_frontend.py`, `tests/test_mcp_end_to_end.py`) still pass.

## 5. Checks

- [ ] 5.1 Run `ruff check src tests examples`, `mypy src/chatinho examples`, `pytest -q` and `openspec validate --all --strict --no-interactive`; all pass, and pytest shows no "coroutine was never awaited" warning.

## Workflow follow-up

- Archive with `/opsx:archive` after review, which creates `openspec/specs/peer-lifecycle` and folds the rest into `conversation-context` and `openai-connector`.
