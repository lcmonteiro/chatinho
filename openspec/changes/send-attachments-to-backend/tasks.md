# Tasks

## 1. Hooks

- [ ] 1.1 In `src/chatinho/chat_hooks.py`, add `HookKeep` (demands `keep`), `HookLink` (demands `link`) and `HookLocate` (grants `locate`) next to `HookLoad`/`HookForget`, plus a `Locate` protocol. Export all four from `src/chatinho/__init__.py`. Verify `mypy src/chatinho` is clean and `from chatinho import HookKeep, HookLink, HookLocate, Locate` works.
- [ ] 1.2 Add the three hooks to `docs/SPEC.md`'s hook table and give each its own section with an example. Verify `pytest tests/test_architecture.py` passes.

## 2. Session

- [ ] 2.1 Remove `attachments` from `ChatMessage` in `src/chatinho/chat_message.py`, keeping `Attachment` and `Reply`, and update their docstrings. Verify `tests/test_message_store.py` passes.
- [ ] 2.2 In `src/chatinho/chat_session.py`, add `_kept(msg, attachments)`, which awaits the `HookKeep` peer's `keep`, drops the attachments when there is none, and logs and continues when it raises. Build text-only messages at the four posting sites and call `_kept` before `_post`, but not for invocations. Verify with tests in `tests/test_attachments.py`: attachments are kept before any listener receives the message; listeners and `context()` get text only; with no keeper, the text is posted; when `keep` raises, the text is posted and an error is logged; `say`, `ask`, `answer` and command results all keep for their own message id, and the invocation keeps nothing.
- [ ] 2.3 Add `_locate` and the `locate` grant in `_grant`, plus a public `ChatSession.locate`. Verify with tests: a peer declaring `HookLocate` gets the backend's link; without a `HookLink` backend it gets `None`; a raising `link` returns `None` and logs.

## 3. Terminal

- [ ] 3.1 Declare `HookLocate` on `ChatApp` and pass `locate` to `ChatLog`. Create message bodies with `open_links=False` and handle `Markdown.LinkClicked`: absolute links go to `app.open_url`, and relative links (leading `./` stripped) go to `locate(msg_id, name)`, then either open the result or `notify("Not found")`. Verify with mounted tests in `tests/test_chat_app.py` that patch `open_url` and `notify`: found opens the link, not found says "Not found", and an absolute link opens without calling `locate`. Also check that the Textual-shadowing tests in `tests/test_architecture.py` still pass.

## 4. Database backend

- [ ] 4.1 In `src/chatinho/backends/database.py`, add the `attachments` table and declare `HookKeep` and `HookLink`. Implement `keep` (merge rows off the loop) and `link` (write to a temp cache directory on demand and return `Path.as_uri()`, or `None`). Remove the cache in `shutdown()`. Verify with tests in `tests/test_database_backend.py`: keep then link returns a `file://` URI whose file holds the data; an unknown name returns `None`; keeping twice is one row; after `shutdown` the cache directory is gone.
- [ ] 4.2 Make `forget` drop the attachments of the messages it drops, in the same transaction. Verify with tests: forgetting a message makes its attachment links `None` while newer messages' links still work, and forgetting everything drops all attachments.
- [ ] 4.3 Verify end to end with a test in `tests/test_database_backend.py`: a session with a file-backed `DatabaseBackend` says a message with an attachment and closes; a new session on the same file can `locate` it and gets a `file://` link to the same content.

## 5. Docs and verification

- [ ] 5.1 Update `docs/SPEC.md`'s "Attachments" section, the `HookSay`/`HookAsk` wording ("attachments go to the backend"), `README.md`'s attachments section (with a note that attachments are untrusted content) and `CLAUDE.md` (the "Attachments" section and layout line) to describe the new flow. Verify `grep -rn "msg.attachments\|ChatMessage.attachments" src docs README.md CLAUDE.md` finds nothing.
- [ ] 5.2 Run the three CI checks, `ruff check src tests examples`, `mypy src/chatinho` and `pytest -q`, plus `openspec validate --all --strict --no-interactive`, and verify all pass.
