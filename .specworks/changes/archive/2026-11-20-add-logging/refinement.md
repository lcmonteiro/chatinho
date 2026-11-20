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

**Reopened after close:** always writing a file was the wrong default. The
user wants an environment variable, `CHATINHO_LOG_PATH`, to turn logging on;
when it is not set, logging is off.

## Outcomes

- Logging is off unless `CHATINHO_LOG_PATH` is set: with the variable unset
  or empty, `ChatSession.run()` writes no file and leaves logging exactly as
  it was before this change.
- With `CHATINHO_LOG_PATH=<dir>`, `run()` appends to
  `<dir>/chatinho.<YYYY-MM-DD>.log`, dated by the day the chat started. A
  directory that does not exist is created, for its owner only; a file it
  creates is its owner's only.
- It holds chatinho's records at DEBUG, one per line, each with the time,
  the level, the process and where it came from, so two chats sharing a
  day's file can be told apart.
- The file is enough to follow a chat: peers and commands attached; every
  message by id, sender, addressee, reply-to and length; asks and the status
  they were answered with; commands run; routing decisions; backend load and
  forget; the hive going down and coming back; every failure with its
  traceback.
- The file never holds message text, attachment content or a key.
- The variable is the only switch: no parameter, and no second variable for
  the level.
- `import chatinho`, the test suite, and code that drives `start()`/`close()`
  itself write no file.
- When the directory cannot be created or written, the chat runs anyway,
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

- (After close) `logs.py` holds `open_log()`, called by `run()`, which today
  always writes to `tempfile.gettempdir()`; `log_file(day)` names the file;
  the file and directory tests set `tempfile.tempdir`.

**Assumed:**
- Events and ids without text keep a busy day's file at a few megabytes, so
  no rotation is needed.

## Constraints

- [hard] Logging is off by default; `CHATINHO_LOG_PATH` names the directory
  that turns it on, and it is the only switch. An empty value is unset.
- [hard] The file inside it is always `chatinho.<date>.log`; the level stays
  DEBUG.
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

### After reopening: where the variable is read

- **Variable option A: `open_log()` reads `CHATINHO_LOG_PATH`** and returns
  None when it is unset; `log_file(day, directory)` names the file; `run()`
  is unchanged. One module owns the whole decision, and nothing but the
  variable can turn logging on. Meets every outcome. Effort: S. Touches:
  framework.
- **Variable option B: `run()` reads it** and passes the directory to
  `open_log(directory)`. Meets every outcome too, but makes `open_log`
  usable without the variable, a second way to turn logging on. Effort: S.
  Touches: framework.

## Recommendation

Option A, agreed: it is the only one that meets every outcome without
adding a peer to the room. After reopening: variable option A, agreed:
`open_log()` reads `CHATINHO_LOG_PATH` itself.

## Open Questions

None: the line format, the setup's place in the layers and the events each
specialization logs were settled in the first design, and the variable's
meaning, a missing directory and the level were settled after reopening.

## Candidate Capabilities

- `framework`: modified - `run()` sets up the log file; the session logs its
  events.
- `backends`, `routers`, `commands`, `workspaces`, `connectors`,
  `frontends`, `agents`: modified - each logs its own events, without text
  or keys.
