# Refinement: add-logging

## Problem

When a chat misbehaves there is nothing to read afterwards. chatinho has
loggers in 18 modules, but nothing ever gives them a destination: Python's
last-resort handler prints warnings to stderr, debug and info are dropped,
and while the terminal runs Textual captures stderr, so even the warnings are
lost. What is logged is mostly failures, and most of what a chat does
(messages posted, asks answered, routing, commands, the hive coming and
going) is not logged at all. Multi-peer chats and the hive have made "what
happened, in what order" hard to answer from the screen alone.

## Outcomes

- After any `ChatSession.run()`, the file `chatinho.<YYYY-MM-DD>.log` exists
  in the system's temporary directory (`/tmp` on Linux and macOS,
  `$PREFIX/tmp` on Termux), dated by the day the chat started and appended
  to.
- It holds chatinho's records at DEBUG, one per line, each with the time,
  the level, the process and where it came from, so two chats sharing a
  day's file can be told apart.
- The file is enough to follow a chat: peers and commands attached; every
  message by id, sender, addressee, reply-to and length; asks and the status
  they were answered with; commands run; routing decisions; backend load and
  forget; the hive going down and coming back; every failure with its
  traceback.
- The file never holds message text, attachment content or a key.
- Logging is always on: there is no parameter or variable to move or silence
  it.
- `import chatinho`, the test suite, and code that drives `start()`/`close()`
  itself write no file.
- When the temporary directory cannot be written, the chat runs anyway,
  without the file, and says so once on stderr.
- A program that configured logging itself still receives chatinho's
  records; chatinho's file holds only chatinho's records.

## Context

**Observed:**
- 18 modules hold `logger = logging.getLogger(__name__)`, with 49 calls,
  4 of them `info`. About 20 sizable modules log nothing: among them
  `builder.py`, `routers/simple.py`, `commands/workspace.py`,
  `backends/hive_cache.py`, the key sources and the hive's store and CLI.
- No handler is installed anywhere; the only logging setup is the hive's
  filter on `uvicorn.access` that masks `?key=` (`hive/app.py`).
- Textual replaces stdout/stderr with a capture while the app runs
  (`textual/app.py`, `_PrintCapture`).
- `ChatSession.run()` (`session.py`, `framework`) is the entry point that
  owns the loop: every example and both builders end in it; tests drive
  `start`/`close` instead.
- Failures inside peers are already logged with tracebacks by the session;
  error replies name the exception type and never its message, which may
  echo a prompt (`framework` living docs).
- `tests/test_architecture.py` requires every file at the package root to
  belong to a layer.

**Assumed:**
- `tempfile.gettempdir()` resolves `/tmp` on Linux/macOS and `$TMPDIR` on
  Termux, which is what "the system's tmp directory" means here.
- Events and ids without text keep a busy day's file at a few megabytes, so
  no rotation is needed.

## Constraints

- [hard] The file goes to `<tempdir>/chatinho.<date>.log`; no parameter, no
  environment variable, no way to turn it off.
- [hard] Only `ChatSession.run()` sets it up; importing chatinho configures
  nothing (Python's rule for libraries).
- [hard] The handler is attached to the `chatinho` logger, not the root, and
  records still propagate.
- [hard] No message text, attachment content or key in any record.
- [hard] A log that cannot be opened never stops a chat.
- [hard] Logging never blocks the loop noticeably and stays stdlib-only in
  the core.
- [hard] The hive server is out of scope: it keeps uvicorn's console output
  and writes no file.
- [soft] %-style logging calls, as the conventions say; the f-string calls
  inherited by the connectors may be converted where touched.

## Options

### Option A: Log calls in the session and in each specialization

`run()` attaches a file handler to the `chatinho` logger. The session logs
each event once, where it happens: attach, post, ask and its answer, invoke,
route, forget, failures. Each specialization logs its own events (backend
open/load/forget, hive down/up, worktree create/merge/drop, LLM router
choice, MCP client connect).

- **Pros:** one line per event at its source; sees everything, including
  what never becomes a message; no API or roster change.
- **Cons:** touches most of the package; each new feature must remember to
  log.
- **Effort:** M
- **Touches:** framework, backends, routers, commands, workspaces,
  connectors, frontends, agents
- **Outcomes:** meets all.

### Option B: A built-in listening peer attached by `run()`

A peer declaring `HookListen` that logs every message it hears.

- **Pros:** no change to the session's code paths.
- **Cons:** a peer in every roster, in `/help` and in the MCP `peers` tool;
  hears only messages, so attach, routing, failures and hive outages are
  missed.
- **Effort:** S
- **Touches:** framework
- **Outcomes:** meets the file, privacy and setup outcomes; fails "follow a
  chat" beyond messages.

### Option C: The file plus log calls in the specializations only

- **Pros:** the session stays untouched.
- **Cons:** the conversation itself (posts, asks, routing) is not followed.
- **Effort:** S-M
- **Touches:** the specializations
- **Outcomes:** fails "the file is enough to follow a chat".

## Recommendation

Option A, agreed: it is the only one that meets every outcome without
adding a peer to the room.

## Open Questions

- The exact line format, and the field that names a chat when several share
  a day's file (process id, a session id, the frontend's name). (who can
  answer: design)
- Where the setup function lives in the layers (in the framework beside
  `session.py`, or a stdlib part). (who can answer: design)
- The exact list of events each specialization logs, and their levels.
  (who can answer: specify)

## Candidate Capabilities

- `framework`: modified - `run()` sets up the log file; the session logs its
  events.
- `backends`, `routers`, `commands`, `workspaces`, `connectors`,
  `frontends`, `agents`: modified - each logs its own events, without text
  or keys.
