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
- An ask is resolved only by a reply from the peer it was asked of. A reply from anyone else is heard like any other message and leaves the ask waiting.
- `add_connector` never hands out an id that is already taken. Automatic numbering skips ids pinned with `@connector(name, id=…)`.
- **BREAKING**: `ask()` returns a `Reply` holding the answer's text and its status (`answered`, `asked` or `error`, the "too many nested asks" reply included) instead of the text alone, so the asker can tell a failure from an answer. (First implemented as raising `PeerError`; changed at review in [lcmonteiro/chatinho#42](https://github.com/lcmonteiro/chatinho/pull/42).)
- The agent's `ask_<peer>` tool hands the model the peer's `Reply` itself, status included, rather than folding an error into prose; an exception becomes an `error` `Reply` naming its type. LangChain passes a non-text tool result as `str()`, so the model reads the `Reply`'s repr.
- The database backend keeps each message's `status` and gives it back on load, so `Query(errors=False)` still leaves failed replies out after a restart.
- ~~Each builder needs only its own extra.~~ Reverted at review ([lcmonteiro/chatinho#42](https://github.com/lcmonteiro/chatinho/pull/42)): `builder.py` keeps importing both frontends, so each builder still needs `chatinho[tui,mcp]`.
- **BREAKING**: `DatabaseBackend` refuses keyword arguments it does not know (`TypeError`) instead of silently swallowing them.
- `copy_key` validation errors name `copy_key`, not `quit_key`.

**Code quality (no behaviour change)**

- `OpenAIConnector` and `AgentConnector` share one memory helper: what `memory` selects, minus the question, and how each speaker is labelled.
- Removals:
  - `HelpCommand`'s unused `HookSay`;
  - the second `COMMAND_PREFIX`;
  - the thread-id field `ChatFrontend` uses only as a "mounted" flag;
  - the hand-rolled reply-quote preview, in favour of `preview_of`.
- ~~`ChatLog.sync()` reads the conversation once per sync.~~ Reverted at review ([lcmonteiro/chatinho#42](https://github.com/lcmonteiro/chatinho/pull/42)).
- Bubble widths are measured in terminal cells, so wide characters (CJK, emoji) are no longer under-counted.
- Stale docstrings are corrected in `hooks.py`, `session.py`, `builder.py` and `composer.py`, along with the "eighteen hooks" description in `pyproject.toml`.

**Workflow**

- CI runs the tests on Python 3.13 as well as 3.12.
- `openspec/config.yaml` carries the project's conventions as context for generated artifacts.
- The OpenSpec integration's duplicate delivery (each operation as both a skill and a command) was investigated. Both are kept by decision, because the skills-only setting is per machine and renames the `/opsx:*` commands; see task 8.3.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `message-delivery`: an ask is resolved only by the asked peer's reply. The terminal's own notices are not said into the conversation.
- `answer-details`: `ask` returns the answer's `Reply`, status included, and the archive keeps `status`. This replaces "`ask` MUST keep returning the answer's text" and "the archive need not keep the status".
- `conversation-context`: the archive keeps `status`, so `Query(errors=False)` holds across a restart.
- `peer-lifecycle`: ids are unique, and automatic numbering skips pinned ids.
- ~~`mcp-server`~~: Reverted at review ([lcmonteiro/chatinho#42](https://github.com/lcmonteiro/chatinho/pull/42)); `McpFrontend` still takes the first reply to a question.
- ~~`package-layout`~~: Reverted at review ([lcmonteiro/chatinho#42](https://github.com/lcmonteiro/chatinho/pull/42)); no requirement changes.

## Impact

- **Code:**
  - `src/chatinho/session.py`: `add_connector`, `_post`, `ask`.
  - `src/chatinho/builder.py`: docstrings only.
  - `src/chatinho/backends/database.py`
  - `src/chatinho/frontends/chat/`: `__init__.py`, `messages.py`, `composer.py`.
  - `src/chatinho/connectors/`: `openai.py`, `agent.py`, sharing the new `src/chatinho/helpers/memory.py`.
  - `src/chatinho/commands/help.py`
  - `src/chatinho/hooks.py`
- **Tests:**
  - `test_chat_frontend.py` and `test_command_suggestions.py` change what they assert, and tests that compared `ask()` to a string read `.text`.
  - New regression tests cover each reproduced defect.
- **API:**
  - `ask()` callers read `.text` (and `.status`) from the returned `Reply`.
  - `DatabaseBackend(**kwargs)` no longer accepts unknown keywords.
- **Data:** the archive schema gains a `status` column. It is the baseline, like `asked_of`: archives from before it are not migrated.
- **Docs and tooling:** `CLAUDE.md` (the `ask` result and the archive policy), `docs/SPEC.md` (the `HookAsk` section), `README.md`, `.github/workflows/tests.yml`, `openspec/config.yaml` and `.claude/`.
