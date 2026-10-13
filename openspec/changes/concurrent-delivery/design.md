# Design

## Context

`ChatSession` gives every peer an `asyncio.Queue` and one `_drain` task (`session.py`).
`_post` stores the message, then calls `put_nowait` on the queue of each listener and of the
addressee. `_drain` awaits `_deliver` for one message before taking the next. `close()` joins every
queue (five seconds), then cancels the drain tasks. A peer added before `start()` gets its queue at
`add_connector` and its drain task at `start()`, so anything said earlier waits in the queue.

The conversation's order already lives elsewhere: `_store.add` runs before anything is queued, and
the database backend loads by `timestamp`. The three `listen` implementations (terminal repaint,
database write, MCP frontend future) do not depend on hearing messages in order. Commands are not
peers: `invoke` awaits `execute` in the caller's own task, and the terminal awaits `invoke` inside
its input handler.

## Goals / Non-Goals

**Goals:**
- Remove serial delivery and the queue state that exists only to support it.
- Make recursion safe by bounding it, not by forbidding it.
- Keep every public signature. The only API addition is `ChatSession(max_depth=8)`.

**Non-Goals:**
- A per-peer concurrency limit. Nothing needs one yet, and a peer can hold its own semaphore.
- Timeouts on `ask`. A slow answer is not an error, and the depth limit stops loops.
- Changing how commands run: they stay inline in the caller's task. Only the terminal stops
  awaiting them in its handler.

## Decisions

### One task per delivery, tracked in one set
`_post` stores the message, then starts one task per recipient, running `_deliver(peer, msg)`. The
session keeps those tasks in a set and drops each one when it finishes. The exception handling now
in `_drain` (log it and carry on) moves into a small wrapper around each task.
- *Alternative: keep the queues and drain them with N workers.* This still needs N, still deadlocks
  at depth N + 1, and keeps state that has no remaining purpose.
- *Alternative: answers in tasks, listens serial.* Rejected: no listener needs order (see Context),
  and two delivery paths are harder to reason about than one.

### Messages before start wait in a held list
A peer is *running* once `start()` has initialized it. Until then, its deliveries go to a list of
`(peer, message)` that `start()` flushes, in order, as tasks. This keeps today's "said before start
is heard after start" behaviour, and also covers a peer added after start until `start()` is called
again.

### Depth in a ContextVar, depth per question in a dict
Each question's depth is stored in `self._depth[msg.id]` when the question is posted. A question is
an ask, an addressed `say(to=...)`, or a `say` routed to the only answerer.
- **How depth is computed.** It is `_ANSWERING.get() + 1`. `_ANSWERING` is a module-level
  `ContextVar[int]` that defaults to 0.
- **Answering.** The delivery task sets `_ANSWERING` to the question's depth before calling
  `answer`.
- **Listening.** It sets it to 0 before calling `listen`. Tasks copy their creator's context, so the
  reset is needed, otherwise a listener would inherit its speaker's depth.
- **Past the limit.** When a question's depth exceeds `max_depth`, `_deliver` does not call
  `answer`. It posts `Reply("too many nested asks (limit N)", status=ERROR)` as the peer's answer,
  through the same path as a returned Reply, so the waiting `ask` resolves and the error is in the
  conversation. Listeners still hear the question.
- **Cleanup.** The entry in `_depth` is removed when the question's delivery ends.
- **An answer past the limit is dropped, not answered.** An answer to an addressed `say` is handed
  back to the asker's `answer` (nobody is waiting on it). If one of those is past the limit, it is
  dropped with a warning instead of getting the error reply. Otherwise two peers that answer
  answers would trade error replies forever.
- *Alternative: a depth field on `ChatMessage`.* Rejected: it would be public, archived and part of
  the message model for something only the session uses.
- *Alternative: an ancestry chain to detect cycles.* Rejected: A -> B -> A is legitimate, and a
  depth limit also stops long non-cyclic chains.

### close(): wait, then cancel, then fail the waiters
`close()` stops new deliveries from starting, waits on the in-flight set with
`asyncio.wait(timeout=5)`, logs a warning if it times out, then cancels what remains. Every ask
still pending gets `RuntimeError("the chat closed")` set on its future, so no caller hangs. Then
`shutdown()` runs as today.

### The terminal runs commands in a worker
`on_command_input_submitted` calls `self.run_worker(self.command(name, args), exclusive=False)`
instead of awaiting it. Textual cancels workers when the app exits, and `close()` cancels any
delivery the command started. Plain text and `@peer` already return after posting.

### The database backend owns its ordering
`DatabaseBackend` runs all database work on its own single-thread executor (created in
`initialize`, shut down in `shutdown`) instead of the loop's default pool. Writes then cannot race
on the shared in-memory SQLite connection (`StaticPool`), and each write commits in arrival order.
- *Alternative: an `asyncio.Lock` around each call.* Equivalent, but it still borrows threads from a
  pool other code uses.

### Connectors checked for concurrent calls
- **`OpenAIConnector`.** Concurrent questions are already handled: the client swap in `_own_client`
  has no `await` between the check and the assignment, and `_using` counts the requests in flight.
- **`McpConnector`.** It shares one FastMCP `Client` and enters it with `async with` for every
  question. That is safe only if the client's context is reentrant across tasks. A test confirmed
  it is: three questions at once on one client overlap and each gets its own answer. So the
  connector is unchanged.

## Risks / Trade-offs

- [A third-party peer relied on one message at a time] → Breaking change noted in the proposal; the
  docs say a peer that needs order holds an `asyncio.Lock` itself.
- [Unbounded tasks if a flood of messages arrives] → The same messages would sit unbounded in queues
  today; a per-peer limit stays a deliberate non-goal until something needs it.
- [Tests that observed timing through `asyncio.sleep(0.02)` "let its queue run"] → Rewritten to
  assert after `close()`, which waits for in-flight deliveries.
- [Listeners hear a reply before the question when the question's listener is slow] → Allowed by
  the spec; the store's order is what anything reading the conversation sees.

## Migration Plan

Single release. There is no data migration, and the archive format is unchanged. Rollback is
reverting the change.
