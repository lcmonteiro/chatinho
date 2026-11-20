# Review: add-logging

Base: `<!-- base branch -->`

## Findings

<!-- One line per drift between code, spec and design (API), from `specworks review` and from
reading the diff. `- [ ] R<n>` while open, `- [x] R<n>` once resolved. Write
"None." when there are no findings. -->

- [x] R1 **quality** DatabaseBackend logs its database URL as given (src/chatinho/backends/database.py:151), so a URL with a password (postgresql://user:pass@host/db) now lands in the shared log file; REQ-CORE-036/REQ-BACK-014 say no record holds a key
  - **Proposal**: back to code: log the URL with its password masked (sqlalchemy's make_url(url).render_as_string(hide_password=True)), with a test that a URL holding a password never reaches a record
  - **Decision**: back to code: log the database URL with its password masked (sqlalchemy make_url(url).render_as_string(hide_password=True)), with a test that a URL holding a password never reaches a record
  - done in code: DatabaseBackend logs its URL with the password masked (render_as_string(hide_password=True)); test_the_database_archive_never_logs_its_password fails on the old code
  - confirmed in review: checked: database.py logs make_url(...).render_as_string(hide_password=True); the test fails on the old code and passes
- [x] R2 **quality** The log file is created with the process umask (src/chatinho/logs.py, open_log), usually 0644, so on a shared machine anyone can read which peers, URLs and ids a chat had
  - **Proposal**: back to code: create the file owner-only (0600) when open_log creates it, leaving an existing file's mode alone, with a test of the mode on POSIX
  - **Decision**: back to code: create the log file owner-only (0600) when open_log creates it, leaving an existing file's mode alone, with a test of the mode on POSIX
  - done in code: open_log creates the file 0600 and leaves an existing file's mode; two tests in test_log_file.py, the first fails on the old code
  - confirmed in review: checked: logs.py creates the file 0600 via os.open before the FileHandler, an existing file keeps its mode; both tests pass, the first fails on the old code
- [x] R3 **quality** McpConnector logs a failed ask with the exception's repr (src/chatinho/connectors/mcp.py:169, '%r'), which can carry the remote side's message and so text of the conversation (REQ-CONN-025: no record holds the prompt or the answer)
  - **Proposal**: back to code: log only the error's type there, as OpenAIConnector and AgentPeer do, with a test that a remote error's text never reaches a record
  - **Decision**: back to code: log only the error's type when McpConnector cannot ask its server, with a test that a remote error's text never reaches a record
  - done in code: McpConnector logs a failed ask by the error's type only; test_a_remote_error_s_text_is_not_logged fails on the old code
  - confirmed in review: checked: mcp.py logs type(exc).__name__ only; the test uses a modern-protocol client so the failure is the call's own, and fails on the old code
- [x] R4 **design-gap** The 'attached' records are written at construction, before run() opens the file, so the file never held them; the code half made the 'started' record name every peer with its id and the commands (src/chatinho/session.py, start), which design.md does not say
  - **Proposal**: back to design only: record in design.md's event-records Decision that 'started' names the roster (name=id) and commands, because attaching happens before run() opens the file
  - **Decision**: back to design only: state in design.md's event-records Decision that 'started' names the roster (name=id) and the commands, because peers are attached before run() opens the file
  - done in design: design.md's event-records Decision now says 'started' names the roster as name=id and the commands, and why
  - confirmed in review: checked: design.md's event-records Decision says 'started' names the roster as name=id and the commands, and why
- [x] R5 **test-gap** test_forgetting_is_logged_with_how_many_went asserted forget() returns 3 with no backend, where forget() returns what the archive dropped (0); the code half removed that assertion and kept the logged count (tests/framework/test_session_logging.py)
  - **Proposal**: accept the correction already made: the test now asserts the 'forgot 3' record only
  - **Decision**: accepted: the code half already removed the wrong assertion; the test checks the 'forgot 3' record, which is what AC-CORE-035.7 asks
- [x] R6 **quality** I1: _failed latches a failed open for the whole process (src/chatinho/logs.py:104-114): after the directory is fixed, a later run() in the same process stays silent and off until exit; _open is needed (it keeps a second run() from attaching a second handler and lets close_log() undo the setup)
  - **Proposal**: back to code: drop _failed so each run() retries opening the log (one stderr line per failed run), keep _open; add a test that a run after a failed one opens the file once the directory is fixed
  - **Decision**: back to code: drop _failed so each run() retries opening the log (one stderr line per failed run), keep _open; test that a run after a failed one opens the file once the directory is fixed
  - done in code: _failed is gone: a failed open is not remembered and the next run() retries; _open stays. test_a_run_after_a_failed_one_opens_the_file_once_it_can fails on the old code
  - confirmed in review: checked: no _failed left in logs.py; the retry test fails on the old code and passes; suite 996 passed
- [x] R7 **quality** I2: logging.FileHandler cannot set permissions, so open_log opens the path twice, os.open(..., 0o600) then FileHandler (src/chatinho/logs.py:111-112), and neither refuses a symbolic link, so a link planted at the predictable chatinho.<date>.log in a shared directory gets the log appended to its target; owner-only (0600/0700) is enforced on POSIX only, which nothing says
  - **Proposal**: back to code: open the file once through a FileHandler subclass whose _open passes opener=lambda p, f: os.open(p, f | getattr(os, 'O_NOFOLLOW', 0), 0o600), with a test that a symbolic link at the log path is refused (one stderr line, nothing written to its target); say in CLAUDE.md that owner-only is enforced on POSIX only
  - **Decision**: back to code: open the file once through a FileHandler subclass whose _open uses an opener with os.open(..., flags | O_NOFOLLOW where available, 0o600); test that a symbolic link at the log path is refused; say in CLAUDE.md that owner-only is enforced on POSIX only
  - done in code: the file is opened once through _PrivateFile, a FileHandler whose opener is os.open(..., flags | O_NOFOLLOW where available, 0o600); test_a_symbolic_link_at_the_log_path_is_refused fails on the old code; CLAUDE.md says owner-only and the refused link hold on POSIX only
  - confirmed in review: checked: one open through _PrivateFile with os.open(flags | O_NOFOLLOW, 0o600); the link test fails on the old code and passes; CLAUDE.md states the POSIX-only scope

## Changed files without tags

<!-- Every file `specworks review` lists under untracedSource/untracedTests,
with why it needs no tag (config, refactor, helper of REQ-...) or the
finding that covers it. -->

## Summary

<!-- Two or three lines: what was found, what changed in code, specs and design, and anything sent back to an earlier phase. -->

First round: five findings, all resolved: R1–R3 fixed in code (masked database password, owner-only
log file, MCP errors by type), R4 in design, R5 accepted. Reopened round (`CHATINHO_LOG_PATH` turns
logging on): no findings. REQ-CORE-034's ten criteria are each tested through `run()`, the suite
passes (994 passed, 1 skipped) and leaves no file without the variable.

Reopened after inspection (I1, I2 as R6, R7): `_failed` dropped so the next `run()` retries; the file
opened once through an opener with 0600 and `O_NOFOLLOW` where available; both proved by tests that
fail on the old code; suite 996 passed, 1 skipped.
