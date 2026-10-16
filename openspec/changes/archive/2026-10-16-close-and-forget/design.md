# Design

## Context

See proposal.md for why. The current shape:

- `close()` ends with a loop over every peer and command: `shutdown = getattr(who, "shutdown", None)`, then `shutdown()` in a `try` that logs. Anything it returns is dropped, so an `async def shutdown` only creates a coroutine that never runs (Python warns "never awaited").
- `start()` already handles `initialize()` either way through `_initialize`: call it, and `await` the result if `isawaitable`.
- `OpenAIConnector` keeps `self._client = (digest, AsyncOpenAI)` for its own key and closes rotated-out clients when idle; the current one is never closed. The test double `tests/fakes/llm.py:FakeOpenAI` records `closed`.
- `ChatSession.forget` calls the `HookForget` backend and returns its count, 0 without one. `MessageStore` holds `_messages`, `_index` (by id) and `_replies` (id to the ids answering it); it has no way to drop anything.
- `McpFrontend._attachments_of` calls `_read_link(url)`, which does `open(...).read()` on the loop.

## Goals / Non-Goals

**Goals:**
- One rule for both lifecycle ends: `initialize()` and `shutdown()` may each be a coroutine.
- After `forget`, the session and the archive agree about what exists.

**Non-Goals:**
- Closing what `AgentConnector`'s LangChain model holds. Its clients belong to LangChain and have no public close; reaching into them is a different change.
- Telling the terminal to repaint after `forget`. Nothing calls `forget` from inside the library today. The terminal drops the forgotten messages at its next repaint, which any new message triggers.
- `McpConnector`: it opens its client with `async with` for each question, so it holds nothing between calls.

## Decisions

### 1. Call every shutdown first, then await the coroutines together, once

```python
pending = []
for who in peers_and_commands:
    shutdown = getattr(who, "shutdown", None)
    if callable(shutdown):
        try:
            result = shutdown()
        except Exception:
            logger.error(...)
        else:
            if isawaitable(result):
                pending.append(asyncio.ensure_future(result))
if pending:
    done, late = await asyncio.wait(pending, timeout=self.CLOSE_TIMEOUT)
    # log each exception in done; warn and cancel each in late
```

Synchronous shutdowns keep their order and their behaviour. The asynchronous ones run concurrently, so one slow peer costs the bound once, not once per peer.

**Alternative rejected: awaiting each in turn, each bounded.** It is simpler, but N stuck peers cost N timeouts, which is what the existing bound on deliveries already avoids.

### 2. `OpenAIConnector.shutdown` closes the current client and forgets it

`async def shutdown(self)`: if `self._client` is set, close it and set `_client = None`. By the time `shutdown` runs, `close()` has finished or cancelled every delivery, so no request is still using the client; the per-question clients for lent keys are already closed by their `async with`.

### 3. `MessageStore.forget(before)` rebuilds its maps; the session calls it before the backend

`forget(before)` keeps `[m for m in messages if before is not None and m.timestamp >= before]`, then rebuilds `_index` and `_replies` from what is kept. A reply whose parent was forgotten keeps its `reply_to`, as in the archive. It returns how many it dropped, which `ChatSession.forget` ignores in favour of the backend's count (chosen with the user, so the return value means what it meant).

The session drops from memory first, then asks the backend. If the backend raises, the memory is already consistent with what the caller asked for, and the error propagates as it does today.

### 4. `_read_link` runs in a thread

`data = await asyncio.to_thread(_read_link, url)`. It touches only the file system, so it is safe off the loop.

## Risks / Trade-offs

- [A peer's `shutdown` is now awaited when it returns something awaitable it did not mean to be awaited] → Only a coroutine or future is awaitable, and returning one from `shutdown` only makes sense if it is meant to run. Today such a coroutine is silently dropped, which is the bug.
- [The terminal keeps showing forgotten messages until its next repaint] → Stated in Non-Goals. `forget` has no caller in the library today.
- [`forget` with no backend now changes the conversation] → That is the requested behaviour, and the test that asserted "drops nothing" is rewritten to say what happens instead.

## Migration Plan

One change; nothing stored changes shape. A peer with a synchronous `shutdown` is unaffected.
