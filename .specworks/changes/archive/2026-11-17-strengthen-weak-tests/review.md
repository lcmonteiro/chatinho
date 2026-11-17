# Review: strengthen-weak-tests

Base: `origin/main`

## Findings

None.

Each strengthened or new test was read against its criterion's THEN and against the code, asking whether it fails when the behaviour breaks:

- AC-KEYS-003.2 asserts the variable and the file's path in the message; AC-KEYS-006.1 compares each dotenv source's `path` with `conf/.env` and `.env` (design D4).
- AC-CONN-020.1 proves the `subagents` option reached the agent: a request carried the system prompt `Research.`, a tool result holds `found`, and the connector answers with it. Without the option deep agents has no `researcher`, so none of the three holds (design D1; the risk in design.md did not materialise).
- AC-FRONT-020.11 reads one `WARNING` from the clipboard logger naming `termux-clipboard-set`, for each of the three failures (design D2).
- AC-FRONT-025.6 is gone from tests and code, as a duplicate of AC-FRONT-025.5, whose test is unchanged and covers the same path. AC-FRONT-025.9 checks `is_error` and that the tool error's content is exactly `quota exceeded` (design D3). `specworks check` warns that the MODIFIED REQ-FRONT-025 block drops AC-FRONT-025.6; that drop is the proposal's, on purpose, with its test removed, and the ID is retired.
- AC-CMD-006.1-3 drive `/test` through a session and read its says as `TOOL` after `close()`, in order, the count checked against the conversation's own length at that point, and the answer naming who ran it (design D5).
- AC-CMD-002.3 checks the text through the session and the empty attachments through `execute`; AC-CMD-003.2 checks the refused drop left dev listed with its 1 commit ahead and its commit on `peer/dev`.
- AC-ROUTE-005.1 checks the reply is posted replying to the user's say with `to is None`.
- AC-WS-001.4 (`view=object`, `TypeError` naming `WorkspaceView`: no other check fires on that input), AC-WS-002.5 (a file and a missing path), AC-WS-002.6 (the provider's base and the new worktree's HEAD are the detached sha, on branch `peer/dev`).
- AC-CORE-011.5: the dead `try/except RuntimeError: pass` is gone; the ask is awaited directly and passes (design D6).

The only source change is the `@req REQ-CMD-006` tag on `TestCommand` (`src/chatinho/commands/test.py:9`), which does what REQ-CMD-006 says. No interface changed (design.md `## Interfaces`: none). The suite passed whole (826 tests) with no change to library behaviour, so no strengthened test exposed a bug and no `fix-<name>` change is needed.

## Changed files without tags

- None: `specworks review` lists no untraced source or test file.

## Summary

No drift: every strengthened criterion is asserted by its test, the one code change is the REQ-CMD-006 tag, and the specs and design need no change. AC-FRONT-025.6 was removed on purpose (the `specworks check` warning about it is expected). Out of scope, for a future change: AC-FRONT-025.5's test still overrides the peer's `answer` through `session._peers()` rather than passing a failing peer, which works but reaches past the public interface.
