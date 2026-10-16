# Proposal

## Why

A codebase review found defects that the 595 passing tests do not catch. Each one was reproduced with a script:

- Every demo sends its welcome text to the model as if the user had typed it.
- An unknown `/command` is put to the model too.
- Any peer's reply resolves another peer's `ask`.
- An automatically numbered peer silently replaces one pinned to the same id.
- `ask()` returns an `ERROR` reply as if it were an answer.
- Failed replies come back into the model's memory after a restart.

The review also found duplicated code, stale documentation and workflow overhead. This change acts on the review's whole action plan, in its priority order.

## What Changes

**Behaviour**

- The terminal no longer *says* its own notices:
  - the welcome text is shown at the top of the log but never posted to the conversation;
  - "Unknown command" and "/x failed" become notifications.
- An ask is resolved only by a reply from the peer it was asked of. A reply from anyone else is heard like any other message and leaves the ask waiting. The MCP frontend applies the same rule to its open questions.
- `add_connector` never hands out an id that is already taken. Automatic numbering skips ids pinned with `@connector(name, id=…)`.
- **BREAKING**: `ask()` raises `PeerError` when the answer's status is `error`. This includes the "too many nested asks" reply. `PeerError` is a new public exception carrying the reply's text. Answers with status `answered` or `asked` still return their text.
- The database backend keeps each message's `status` and gives it back on load, so `Query(errors=False)` still leaves failed replies out after a restart. An existing archive gains the column on `initialize()`, with every old row counted as `answered`.
- `build_chat_session` needs only `chatinho[tui]`, and `build_mcp_session` needs only `chatinho[mcp]`. Each builder imports its own frontend when it is called.
- **BREAKING**: `DatabaseBackend` refuses keyword arguments it does not know (`TypeError`) instead of silently swallowing them.
- `copy_key` validation errors name `copy_key`, not `quit_key`.

**Code quality (no behaviour change)**

- `OpenAIConnector` and `AgentConnector` share one memory helper: what `memory` selects, minus the question, and how each speaker is labelled.
- Removals:
  - `HelpCommand`'s unused `HookSay`;
  - the second `COMMAND_PREFIX`;
  - the thread-id field `ChatFrontend` uses only as a "mounted" flag;
  - the hand-rolled reply-quote preview, in favour of `preview_of`.
- `ChatLog.sync()` reads the conversation once per sync, not once per new message.
- Bubble widths are measured in terminal cells, so wide characters (CJK, emoji) are no longer under-counted.
- Stale docstrings are corrected in `hooks.py`, `session.py`, `builder.py` and `composer.py`, along with the "eighteen hooks" description in `pyproject.toml`.

**Workflow**

- CI runs the tests on Python 3.13 as well as 3.12.
- `openspec/config.yaml` carries the project's conventions as context for generated artifacts.
- The OpenSpec integration is regenerated with one delivery mode, so each operation is installed once instead of as both a skill and a command.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `message-delivery`: an ask is resolved only by the asked peer's reply. The terminal's own notices are not said into the conversation.
- `answer-details`: `ask` raises `PeerError` on an `error` answer, and the archive keeps `status`. This replaces "`ask` MUST keep returning the answer's text" and "the archive need not keep the status".
- `conversation-context`: the archive keeps `status`, so `Query(errors=False)` holds across a restart.
- `peer-lifecycle`: ids are unique, and automatic numbering skips pinned ids.
- `mcp-server`: each open question is resolved only by the reply of the peer it asked.
- `package-layout`: each builder needs only its own frontend's extra. This replaces "The builders need both frontend extras".

## Impact

- **Code:**
  - `src/chatinho/session.py`: `add_connector`, `_post`, `ask`.
  - `src/chatinho/message.py`: `PeerError`.
  - `src/chatinho/__init__.py`: the export and the lazy table for the builders.
  - `src/chatinho/builder.py`
  - `src/chatinho/backends/database.py`
  - `src/chatinho/frontends/chat/`: `__init__.py`, `messages.py`, `composer.py`.
  - `src/chatinho/frontends/mcp.py`
  - `src/chatinho/connectors/`: `openai.py`, `agent.py`, plus a shared helper.
  - `src/chatinho/commands/help.py`
  - `src/chatinho/hooks.py`
- **Tests:**
  - `test_package_layout.py` and `test_chat_frontend.py` change what they assert.
  - New regression tests cover each reproduced defect.
- **API:**
  - New `PeerError` export, bringing the public names to 66.
  - `ask()` callers that relied on receiving error text must catch `PeerError`.
  - `DatabaseBackend(**kwargs)` no longer accepts unknown keywords.
- **Data:** existing SQLite and other SQL archives get a `status` column added in place, the first time a backend opens them.
- **Docs and tooling:** `CLAUDE.md` (the public-API count, the archive policy and the builder extras), `docs/SPEC.md` (the `HookAsk` section), `README.md`, `.github/workflows/tests.yml`, `openspec/config.yaml` and `.claude/`.
