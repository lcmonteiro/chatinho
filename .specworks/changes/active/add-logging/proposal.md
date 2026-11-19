# Proposal: add-logging

## Why

chatinho's loggers have no destination, so their records are lost (and while
the terminal runs even warnings vanish into Textual's capture), and what is
logged is mostly failures. Every chat run with `ChatSession.run()` writes a
log file a person can read afterwards to follow what happened (refinement:
Option A).

## What Changes

- **`run()` writes the log file.** Before starting, `ChatSession.run()` adds
  one handler to the `chatinho` logger that appends to
  `<tempdir>/chatinho.<YYYY-MM-DD>.log` (`tempfile.gettempdir()`; the date the
  handler was added, in local time), at DEBUG, one line per record with the
  time, level, process id and logger name. No parameter and no environment
  variable change it. It is added once per process: a second `run()` reuses
  it. Records still reach the program's own handlers exactly as before: at
  the levels they reached them before, never more.
- **An unwritable directory costs the file, not the chat.** The chat runs
  without the file and one line on stderr names the path and the reason.
- **Nothing else configures logging.** `import chatinho`, `start()`/`close()`
  driven by hand, and the test suite write no file.
- **The session logs its events** at DEBUG or INFO: start and close, every
  peer, command and role attached (name and id), every message posted (id,
  sender, addressee, reply-to, status, length, number of attachments), each
  ask's outcome, each command run, routing decisions, context loaded and
  forgotten.
- **The specializations log their own events:** `DatabaseBackend` and
  `HiveBackend` what they load, forget and send; the OpenAI and MCP
  connectors each request and its outcome with its duration; `AgentPeer`
  each run, its duration and every rebuild of its graph; `GitWorktrees` each
  merge and drop.
- **No record holds message text, attachment content or a key**, in the
  session or in any specialization.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `framework`: adds the log file `run()` sets up, the session's event
  records, and the rule that no record carries text or keys.
- `backends`: adds the records `DatabaseBackend` and `HiveBackend` write of
  what they load, forget and send.
- `connectors`: adds a record of each model or server request and its
  outcome.
- `agents`: adds a record of each run and each graph build.
- `workspaces`: adds a record of each merge and drop.

## Related requirements

- REQ-CORE-016 left: `run()` gains the file under its own requirement;
  starting, serving and closing are unchanged.
- REQ-CORE-012, REQ-CORE-017, REQ-CORE-023, REQ-CORE-024, REQ-CORE-032 left:
  they mention logging a failure, which stays as it is; the new records sit
  beside them.
- REQ-BACK-009, REQ-BACK-012 left: the hive's key is still never logged, and
  its refused-key error is unchanged.
- REQ-ROUTE-003, REQ-ROUTE-009 left: routers keep their warnings; the
  decision itself is logged by the session.
- REQ-CONN-004 left: a lent key still wins; the new records name no key.
- REQ-WSM-006, REQ-WSM-009 left: "log" there is `git log`, not logging.
- REQ-WS-004 left: worktrees still outlive the chat; only the records are
  new.
- REQ-CONN-019, REQ-CONN-022, REQ-FRONT-001, REQ-FRONT-003, REQ-FRONT-004,
  REQ-FRONT-005, REQ-FRONT-007, REQ-FRONT-014, REQ-FRONT-016, REQ-FRONT-020,
  REQ-WSM-001 left: they match "log" as the chat log widget or a word in
  passing; nothing about them changes.

## Impact

- `session.py` (setup in `run()`, event records), a new framework module for
  the setup (stdlib `logging`, `logging.handlers`, `tempfile`), registered in
  the framework layer of `tests/test_architecture.py`.
- `backends/database.py`, `backends/hive.py`, `connectors/openai.py`,
  `connectors/mcp.py`, `support/kits/agent/peer.py`, `workspaces/git.py`:
  new log calls.
- CLAUDE.md and the framework's living docs describe the file.
- No new dependency, no API change, no new public name.

## Out of Scope

- The hive server (`chatinho-hive serve`): it keeps uvicorn's console output
  and writes no file.
- Moving, silencing or changing the level of the file: there is no parameter
  or variable, by decision.
- Rotation or cleanup of old log files.
- New records in the routers, the commands and the frontends: what they do
  reaches the session as a route, an invocation or a message, and the
  session logs it there.
- Converting every inherited f-string log call; only the calls touched are
  brought to %-style.

## Assumptions

- The date is the local date when the handler is added; a chat running past
  midnight keeps writing to its first day's file.
- The process id is what tells two chats sharing a day's file apart.
- Writing is handed to a background thread (`QueueHandler` and
  `QueueListener`), so a slow disk never blocks the loop.
