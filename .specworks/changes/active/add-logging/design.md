# Design: add-logging

## Context

See `proposal.md`. Today 18 modules hold a `logging.getLogger(__name__)`
logger, every one of them under `chatinho.`, and nothing installs a handler:
a record reaches the root logger's handlers, or Python's last-resort handler
(WARNING and above, to stderr). The framework is four files (`session.py`,
`hooks.py`, `message.py`, `query.py`, listed in `FRAMEWORK` in
`tests/test_architecture.py`), imports only the standard library, and
`ChatSession.run()` is the one place that owns the process.

## Goals / Non-Goals

**Goals:**
- One file per day in the temporary directory, opened by `run()` only, at
  DEBUG, written off the loop.
- The program's own logging sees exactly what it saw before.
- Event records at the source, carrying ids, counts and states, never text.

**Non-Goals:**
- Any parameter, variable or public name to configure the file.
- Rotation, cleanup, or structured (JSON) lines.
- Records in the routers, the commands, the frontends or the hive server.

## Decisions

### A framework module, `logs.py`, opened from `run()`

`src/chatinho/logs.py` holds the setup and `run()` calls `open_log()` before
`asyncio.run`. It is framework because `session.py` needs it and the
framework may import only itself; it uses only `logging`, `logging.handlers`,
`queue`, `tempfile`, `atexit` and `datetime`. Putting it in a part was
rejected: the framework cannot import a part. Putting it in `__init__.py` or
the builders was rejected by the refinement (import must configure nothing,
and a bot built by hand runs too). Serves: REQ-CORE-034.

### The `chatinho` logger stops propagating and forwards instead

To write DEBUG to the file, the `chatinho` logger's level must be DEBUG; with
`propagate` on, every DEBUG record would then reach the program's root
handlers, which usually have no level of their own (`basicConfig` sets the
level on the logger, not the handler). So `open_log()`:

1. remembers the threshold the program had: the `chatinho` logger's own
   level when the program set one, otherwise "the root logger's level, read
   at each record";
2. sets the `chatinho` logger to DEBUG and `propagate = False`;
3. adds a `QueueHandler` feeding a `QueueListener` thread that writes the
   file;
4. adds `_Forward`, a handler that passes a record on to the root logger
   (`logging.getLogger().handle(record)`, which falls back to the
   last-resort handler as before) only when its level reaches that
   threshold.

So the program's handlers get what they got before, and only that.
Alternatives: a filter on the root handlers (we do not own them, and the
program may add some later); leaving propagation on (DEBUG floods the
program's console). Serves: REQ-CORE-034 (AC-CORE-034.4, AC-CORE-034.5).

### Opened once per process, and the queue keeps the loop free

A module-level state holds the path, the listener and the handlers: a second
`open_log()` returns the same path and adds nothing (AC-CORE-034.2). The
file handler is a `FileHandler(path, mode="a", encoding="utf-8")` opened at
once, so an unwritable directory fails in `open_log()`, which prints one line
to stderr (`chatinho: cannot write the log file <path>: <reason>`), remembers
the failure so later runs stay silent, and returns `None`; the chat runs
without the file (AC-CORE-034.6). The listener is stopped and the file closed
at exit (`atexit`), so the last records are flushed. `close_log()` undoes
everything (handlers removed, level and `propagate` restored); it exists for
the tests and for `atexit`. Serves: REQ-CORE-034.

### The line

```
2026-11-19 15:52:18,123 DEBUG [41237] chatinho.session: posted msg-3f9a… from 1 to 2 replying to msg-1c2… answered 412 chars 0 attachments
```

`LOG_FORMAT = "%(asctime)s %(levelname)s [%(process)d] %(name)s: %(message)s"`.
The process id is what tells chats sharing a day's file apart. The date in
the file's name is `date.today()` when the file is first opened.

### Event records at their source, ids and counts only

Every record uses the module's own `logger` and %-style arguments, and passes
ids (`MessageID`, peer ids), names, statuses, counts and durations; a text is
only ever logged by its length. In the session: `add_connector` and
`add_command` (INFO: name and id), `start` (INFO: messages loaded), `close`
(INFO), `_post` (DEBUG: id, from, to, reply_to, status, length, attachments),
the ask's outcome (DEBUG: question id, reply status; WARNING when cancelled),
`_invoke_for` (DEBUG: name, by), `_routed` (DEBUG: id, chosen or nobody),
`forget` (INFO: count).

Peers, commands and roles are attached in `ChatSession`'s constructor,
before `run()` opens the file, so the `attached` records reach the program's
logging but never the file. The `started` record therefore names the whole
roster as `name=id` pairs and the commands
(`started with peers bot=1, asker=2 and commands none, loaded 0 messages`),
so the file always says who was in the chat (found in review, R4).

**Pinned wording**: the session's records use these words, which the tests
look for beside the ids and counts: `attached` (a peer, command or role),
`started` (with `loaded <n>`), `closed`, `posted`, `answered` (an ask's
outcome, with the reply's status), `ran` (a command, with `by <id>`),
`routed` (with the peer's id, or `nobody`), `forgot` (with the count). The
specializations use `loaded`, `forgot`, `kept`, `linked`, `sent` (a hive
batch: `<n> messages`, `<n> traces`, `<n> waiting`), `took` (a duration in
seconds), `built` (an agent: the factory and `<n> tools`), `merged` and
`dropped`. In the specializations, as REQ-BACK-014,
REQ-CONN-025, REQ-AGENT-013 and REQ-WS-006 list them; durations come from
`time.monotonic()`. The touched f-string calls in the connectors become
%-style. Serves: REQ-CORE-035, REQ-CORE-036, REQ-BACK-014, REQ-CONN-025,
REQ-AGENT-013, REQ-WS-006.

### How the tests reach the file

The file tests point `tempfile.tempdir` at `tmp_path` (monkeypatch) and call
`close_log()` after each, so every test opens its own file; the event tests
use `caplog` on `chatinho` at DEBUG and never open the file. Serves: all.

## Interfaces

Agreed with the user

- `src/chatinho/logs.py` (framework, not exported from `chatinho`):
  - `LOG_FORMAT: str`
  - `log_file(day: Optional[date] = None) -> Path`: the file chatinho.<day>.log in the temporary directory, today by default.
  - `open_log() -> Optional[Path]`: opens the file once per process and returns its path, or `None` when it cannot be written (REQ-CORE-034).
  - `close_log() -> None`: stops writing and restores the `chatinho` logger as it was.
- `src/chatinho/session.py`: `ChatSession.run()` calls `open_log()` first; no signature changes.
- `tests/test_architecture.py`: `FRAMEWORK` gains `logs`.

## Diagrams

No structural change: one framework module is added beside `session.py`,
and no dependency between capabilities changes.

## Risks / Trade-offs

- [The program configures logging after `run()` started] -> the threshold
  reads the root level at each record, so a later `basicConfig` is honoured;
  a later level set directly on `chatinho` is not seen, which is stated in
  the docs.
- [Exception messages may echo a prompt] -> the session never adds text to a
  record; a traceback is logged as the exception wrote it (REQ-CORE-036).
- [A chat past midnight writes to yesterday's file] -> accepted; the name is
  the day the chat started.
- [`/tmp` is shared on a multi-user machine] -> no text and no keys are
  written; the file is created with the process's umask.
- [Records lost if the process is killed] -> the queue is flushed at normal
  exit only; accepted.

## Open Questions

None.
