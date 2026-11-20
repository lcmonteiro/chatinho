# Proposal: add-logging

## Why

The first round made every `ChatSession.run()` write a log file in the
temporary directory, with nothing to turn it off. That was the wrong default:
logging should be opt-in. Reopened so that the environment variable
`CHATINHO_LOG_PATH` turns it on, and with no variable nothing is written
(refinement: variable option A).

## What Changes

- **Logging is off unless `CHATINHO_LOG_PATH` is set.** Unset or empty,
  `run()` writes no file and leaves logging exactly as it was. **BREAKING**
  against the first round, which was never released: a chat that relied on
  the file in the temporary directory now has to set the variable.
- **`CHATINHO_LOG_PATH` names a directory**, and the file in it is still
  `chatinho.<YYYY-MM-DD>.log`, at DEBUG. A directory that does not exist is
  created for its owner only (0700); a file `run()` creates is owner-only
  (0600) and an existing file keeps its mode, which was a review fix of the
  first round and is now a requirement.
- **`open_log()` reads the variable itself**, so nothing but the variable
  turns logging on; `run()` is unchanged. `log_file()` takes the directory.
- Everything else of the first round holds: once per process, off the loop,
  only `chatinho`'s records, the program's own logging unchanged, no text and
  no keys, every event record the session and the specializations write.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `framework`: REQ-CORE-034 is modified: the file is written only when
  `CHATINHO_LOG_PATH` names a directory, in that directory.

## Related requirements

- REQ-CORE-034 modified: the variable decides whether and where the file is
  written.
- REQ-CORE-035, REQ-CORE-036 left: the session's records and the rule that
  none carries text or keys are unchanged; they reach whatever handler is
  there, the file or not.
- REQ-BACK-014, REQ-CONN-025, REQ-AGENT-013, REQ-WS-006 left: the
  specializations' records are unchanged.
- REQ-CORE-016 left: starting, serving and closing are unchanged.

## Impact

- `src/chatinho/logs.py`: `open_log()` reads `CHATINHO_LOG_PATH`, makes the
  directory, and `log_file(day, directory)` names the file.
- `tests/framework/test_log_file.py`: the file tests set the variable
  instead of the temporary directory.
- `CLAUDE.md`, `docs/architecture.md` and the framework's living design say
  logging is opt-in.
- No new dependency, no new public name, `run()`'s signature unchanged.

## Out of Scope

- A level variable, a file name of the caller's choosing, or a parameter on
  `run()`: by decision, the variable is the only switch.
- Rotation or cleanup of old files.
- The hive server, as before.

## Assumptions

- The variable is read when `open_log()` is called, so each `run()` reads it
  until a file has been opened; once open, the file stays for the process.
- `~` in the value is not expanded: the shell expands it before the variable
  is set, and a literal `~` is a directory named `~`.
- The directory is created with its parents (`mkdir -p`), each owner-only.
