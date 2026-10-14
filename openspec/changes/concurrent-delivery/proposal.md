# Proposal

## Why

Every peer has one queue drained by one task, so a peer handles one message at a time. That
serialisation buys nothing for connectors, which keep no conversation state of their own (it
lives in the session's store and in the backend). It also deadlocks recursive asks: when A asks
B and B asks A back, A's queue is still busy with the first question, so both wait forever. The
coming agent connector, whose model asks other peers as tools, makes recursion the normal case.
Separately, the terminal awaits a `/command` inside its input handler, so a slow command freezes
what the user can type.

## What Changes

- Delivery no longer goes through per-peer queues. Each delivery of a message to a peer runs as
  its own task, tracked by the session, so a peer can answer several questions at once and an ask
  can recurse through a peer that is already answering. **BREAKING** for any third-party peer that
  relied on being called one message at a time.
- Asks are bounded in depth. The session tracks how deeply an ask is nested in other asks. Past
  the limit (`ChatSession(max_depth=8)`), the deepest question gets an `ERROR` reply ("too many
  nested asks") without its peer being called, and that reply travels back up like any answer.
- Messages for a peer that has not started yet wait until `start()` starts it, as they do today.
- `close()` waits for the deliveries in flight (five seconds, then a warning), then cancels the
  rest. Asks still waiting when they are cancelled fail rather than hang.
- The frontend never waits on another peer or on a command. Whatever the user sends returns as
  soon as it is posted: the terminal runs `/command` in the background, and its answer arrives as
  a message, as it already does.
- Connectors are documented as stateless. The conversation comes from `context()`, the backend
  alone stores it, and anything a peer holds (a client, a connection) must tolerate concurrent
  calls. The database backend serialises its own database work for that reason.
- Docs follow: the "every peer has its own queue" rule in `CLAUDE.md`, `README.md` and
  `docs/SPEC.md` becomes "every delivery is its own task".

## Capabilities

### New Capabilities
- `message-delivery`: how the session hands messages to peers. This covers concurrent delivery,
  recursive asks and their depth limit, delivery before start and at close, the frontend never
  blocking, and stateless connectors.

### Modified Capabilities
None. No existing spec states the one-at-a-time rule; it lives only in the docs.

## Impact

- `src/chatinho/session.py`: `_queues`, `_drain` and the per-peer tasks are replaced by tracked
  delivery tasks. Changes `_post`, `start`, `close` and `_ask_for`/`_say_for` (nesting depth), and
  adds `ChatSession(max_depth=...)`.
- `src/chatinho/frontends/chat/__init__.py`: `/command` runs as a background worker.
- `src/chatinho/backends/database.py`: database work runs on one dedicated thread, in order.
- `src/chatinho/connectors/mcp.py`, `connectors/openai.py`: checked, and fixed if needed, to
  hold up under concurrent `answer()` calls.
- Tests in `tests/test_chat_session.py` and `tests/test_chat_frontend.py`, plus new tests for
  recursion, depth, concurrency and a non-blocking frontend.
- Docs: `CLAUDE.md`, `README.md`, `docs/SPEC.md`.
- No new dependencies. The planned agent connector builds on this change.
