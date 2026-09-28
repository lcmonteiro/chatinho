# Tasks

## 1. Id generation

- [x] 1.1 In `src/chatinho/chat_message.py`, make `MessageStore.new_id()` return `"msg-" + secrets.token_hex(8)`, remove the counter and its lock, and update the `new_id` and `ChatMessage.id` docstrings. Verify `mypy src/chatinho` and `ruff check src` are clean.
- [x] 1.2 In `tests/test_message_store.py`, replace `test_new_id_increments` with a test that ids match `msg-[0-9a-f]{16}`, and make the thread test generate 10,000 ids across threads and check they are all different. Verify both pass.
- [x] 1.3 In `tests/test_chat_app.py`, change the `say` test to assert the returned id matches the new format and is the stored message's id. Verify it passes.

## 2. Short ids in the terminal

- [x] 2.1 Add `short_id(msg_id)` to `src/chatinho/chat_message.py` (first 7 hex characters of a `msg-` + 16-hex id, anything else unchanged). Verify with tests in `tests/test_message_store.py`: a new-format id gives its 7-character prefix, and `msg-3` or `abc` come back unchanged.
- [x] 2.2 Show `short_id(...)` in `ChatLog`'s header and reply quote, the copy notice title, and `ChatApp`'s reply placeholder, leaving every stored and passed id full. Verify with mounted tests in `tests/test_chat_app.py`: the header shows the short id and not the full one, the placeholder reads `Reply to <short>…`, the copy notice is titled `Copied <short>`, and a reply sent while a target is selected carries the full id in `reply_to`.

## 3. Reopened chats

- [x] 3.1 In `tests/test_database_backend.py`, add a test where a chat on a database file says a message and closes, a new chat on the same file says another, and the archive then holds both messages with different ids and their own texts. Verify it fails on the old counter (reproduce first) and passes with the new ids.

## 4. Docs and verification

- [x] 4.1 Update the two `msg-3` examples in `CLAUDE.md` to the short form (for example `21:15 @meteo · 3f9a1c2`), and mention that headers show a git-style short id. Verify `grep -rn "msg-[0-9]\b" CLAUDE.md docs README.md` finds no generated-id examples.
- [x] 4.2 Run `ruff check src tests examples`, `mypy src/chatinho`, `pytest -q` and `openspec validate --all --strict --no-interactive`, and verify all pass.
