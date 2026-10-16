# Proposal

## Why

Two things a peer or a caller asks the session to let go of are only half let go:

- **`shutdown()` must be synchronous**, so a peer holding an async resource cannot close it when the chat ends. `OpenAIConnector` keeps an `AsyncOpenAI` client (and its HTTP connection pool) for its own key, and nothing ever closes it: `close()` calls `shutdown()` without awaiting, and the connector has no `shutdown` at all. `initialize()` already may be a coroutine; `shutdown()` is the one lifecycle call that may not.
- **`ChatSession.forget(before)` drops archived rows but not the conversation.** `context()` keeps returning the forgotten messages, to every peer's memory and to the terminal, until the session restarts. That makes `forget` look like it did nothing in the session that called it.

Separately, `McpFrontend` reads an attachment's file with a blocking `open().read()` inside a coroutine, against the rule that nothing blocks the loop.

## What Changes

- **`shutdown()` may be `async def`.** `close()` calls every peer's and command's `shutdown`, then awaits the ones that returned a coroutine, together, bounded by `CLOSE_TIMEOUT`. One that raises is logged; one still running at the deadline is cancelled with a warning. A synchronous `shutdown` behaves exactly as before.
- **`OpenAIConnector` closes its own client at shutdown**, with an `async def shutdown`.
- **`forget(before)` also drops those messages from the conversation**, with or without a backend: afterwards `context()` returns nothing older than `before` (nothing at all for `before=None`). The return value is still the archive's count, 0 without a backend, so no caller's arithmetic changes.
- **`McpFrontend` reads attachment files off the loop**, with `asyncio.to_thread`. No behaviour change.

## Capabilities

### New Capabilities
- `peer-lifecycle`: how the session ends a peer's life, starting with `shutdown()`, synchronous or not, at `close()`.

### Modified Capabilities
- `conversation-context`: a new requirement says `forget` drops messages from the conversation as well as the archive.
- `openai-connector`: a new requirement says its client is closed when the chat closes.

## Impact

- `src/chatinho/session.py`: `close()` awaits asynchronous shutdowns; `forget()` drops from the store.
- `src/chatinho/message.py`: `MessageStore.forget(before)`, keeping its index and reply map consistent.
- `src/chatinho/connectors/openai.py`: `async def shutdown`.
- `src/chatinho/frontends/mcp.py`: `_read_link` runs in a thread.
- Tests: `test_chat_session.py` (`test_forget_without_a_backend_drops_nothing` changes meaning: it still returns 0, and now the conversation is empty too), `test_message_store.py`, `test_openai_connector.py`, `test_mcp_frontend.py`.
- Docs: CLAUDE.md's lifecycle table and SPEC.md's lifecycle paragraph and `HookForget` section; the `hooks.py` comment on lifecycle.
