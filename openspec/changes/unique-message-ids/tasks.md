# Tasks

## 1. Id generation

- [ ] 1.1 In `src/chatinho/chat_message.py`, make `MessageStore.new_id()` return `"msg-" + secrets.token_hex(8)`, remove the counter and its lock, and update the `new_id` and `ChatMessage.id` docstrings. Verify `mypy src/chatinho` and `ruff check src` are clean.
- [ ] 1.2 In `tests/test_message_store.py`, replace `test_new_id_increments` with a test that ids match `msg-[0-9a-f]{16}`, and make the thread test generate 10,000 ids across threads and check they are all different. Verify both pass.
- [ ] 1.3 In `tests/test_chat_app.py`, change the `say` test to assert the returned id matches the new format and is the stored message's id. Verify it passes.

## 2. Reopened chats

- [ ] 2.1 In `tests/test_database_backend.py`, add a test where a chat on a database file says a message and closes, a new chat on the same file says another, and the archive then holds both messages with different ids and their own texts. Verify it fails on the old counter (reproduce first) and passes with the new ids.

## 3. Docs and verification

- [ ] 3.1 Update the two `msg-3` examples in `CLAUDE.md` to the new format. Verify `grep -rn "msg-[0-9]\b" CLAUDE.md docs README.md` finds no generated-id examples.
- [ ] 3.2 Run `ruff check src tests examples`, `mypy src/chatinho`, `pytest -q` and `openspec validate --all --strict --no-interactive`, and verify all pass.
