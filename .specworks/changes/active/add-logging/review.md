# Review: add-logging

Base: `<!-- base branch -->`

## Findings

<!-- One line per drift between code, spec and design (API), from `specworks review` and from
reading the diff. `- [ ] R<n>` while open, `- [x] R<n>` once resolved. Write
"None." when there are no findings. -->

- [ ] R1 **quality** DatabaseBackend logs its database URL as given (src/chatinho/backends/database.py:151), so a URL with a password (postgresql://user:pass@host/db) now lands in the shared log file; REQ-CORE-036/REQ-BACK-014 say no record holds a key
  - **Proposal**: back to code: log the URL with its password masked (sqlalchemy's make_url(url).render_as_string(hide_password=True)), with a test that a URL holding a password never reaches a record
  - **Decision**: back to code: log the database URL with its password masked (sqlalchemy make_url(url).render_as_string(hide_password=True)), with a test that a URL holding a password never reaches a record
- [ ] R2 **quality** The log file is created with the process umask (src/chatinho/logs.py, open_log), usually 0644, so on a shared machine anyone can read which peers, URLs and ids a chat had
  - **Proposal**: back to code: create the file owner-only (0600) when open_log creates it, leaving an existing file's mode alone, with a test of the mode on POSIX
  - **Decision**: back to code: create the log file owner-only (0600) when open_log creates it, leaving an existing file's mode alone, with a test of the mode on POSIX
- [ ] R3 **quality** McpConnector logs a failed ask with the exception's repr (src/chatinho/connectors/mcp.py:169, '%r'), which can carry the remote side's message and so text of the conversation (REQ-CONN-025: no record holds the prompt or the answer)
  - **Proposal**: back to code: log only the error's type there, as OpenAIConnector and AgentPeer do, with a test that a remote error's text never reaches a record
  - **Decision**: back to code: log only the error's type when McpConnector cannot ask its server, with a test that a remote error's text never reaches a record
- [ ] R4 **design-gap** The 'attached' records are written at construction, before run() opens the file, so the file never held them; the code half made the 'started' record name every peer with its id and the commands (src/chatinho/session.py, start), which design.md does not say
  - **Proposal**: back to design only: record in design.md's event-records Decision that 'started' names the roster (name=id) and commands, because attaching happens before run() opens the file
  - **Decision**: back to design only: state in design.md's event-records Decision that 'started' names the roster (name=id) and the commands, because peers are attached before run() opens the file
- [x] R5 **test-gap** test_forgetting_is_logged_with_how_many_went asserted forget() returns 3 with no backend, where forget() returns what the archive dropped (0); the code half removed that assertion and kept the logged count (tests/framework/test_session_logging.py)
  - **Proposal**: accept the correction already made: the test now asserts the 'forgot 3' record only
  - **Decision**: accepted: the code half already removed the wrong assertion; the test checks the 'forgot 3' record, which is what AC-CORE-035.7 asks

## Changed files without tags

<!-- Every file `specworks review` lists under untracedSource/untracedTests,
with why it needs no tag (config, refactor, helper of REQ-...) or the
finding that covers it. -->

## Summary

<!-- Two or three lines: what was found, what changed in code, specs and design, and anything sent back to an earlier phase. -->
