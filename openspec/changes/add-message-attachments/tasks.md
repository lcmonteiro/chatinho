# Tasks

## 1. Message model

- [x] 1.1 In `src/chatinho/chat_message.py`, add frozen dataclasses `Attachment(name, media_type, data: bytes)` and `Reply(text, attachments=())`, and add `attachments : Tuple[Attachment, ...] = ()` as the last field of `ChatMessage`. Verify existing `tests/test_message_store.py` and `tests/test_chat_session.py` still pass unchanged.

## 2. Session: every verb attaches

- [x] 2.1 In `src/chatinho/chat_session.py`, give `say(text, *, reply_to=None, attachments=())` and `ask(to, text, *, attachments=())` an `attachments` parameter and build each `ChatMessage` directly with them. Verify with tests in `tests/test_attachments.py`: listeners and the context receive exactly what was attached, and `ask` carries attachments to the peer asked.
- [x] 2.2 Accept `Optional[Union[str, Reply]]` from `answer` (in `_deliver`) and require `Optional[Reply]` from `execute` (in `_invoke_for`, raising `TypeError` for anything else), unwrap the `Reply` in place and build the `ChatMessage` directly, resolve `ask`'s future with the reply text, and have `invoke` return the text. Verify with tests: an answer with a `Reply` carries attachments and `ask` returns the text; a command `Reply` carries attachments and `invoke` returns the text; a string answer is unchanged; a command returning a string raises `TypeError` and posts only the invocation.
- [x] 2.3 Keep the invocation message (`/name args`) free of attachments, and verify with a test that it posts with an empty attachment list.
- [x] 2.4 Make `HelpCommand`, `TestCommand`, the examples and the test commands return a `Reply`. Verify the whole suite passes.

## 3. Hooks, exports and docs

- [x] 3.1 Update the `Say` and `Ask` protocols in `src/chatinho/chat_hooks.py` to take `attachments`, and document the new return types: `answer` returns `str | Reply | None`, `execute` returns `Reply | None`. Export `Attachment` and `Reply` from `src/chatinho/__init__.py` (listed in `__all__`). Verify `mypy src/chatinho` is clean and `from chatinho import Attachment, Reply` works.
- [x] 3.2 Update `docs/SPEC.md` (the `HookSay`, `HookAsk`, `HookAnswer`, `HookExecute` sections and a short "Attachments" subsection), `README.md` (a usage example) and `CLAUDE.md` (the layout line and a short "Attachments ride on the message" section). Verify `pytest tests/test_architecture.py` still passes.

## 4. Verification

- [x] 4.1 Run the three CI checks, `ruff check src tests examples`, `mypy src/chatinho` and `pytest -q`, and verify all pass
- [x] 4.2 Run `openspec validate --all --strict --no-interactive` and verify it passes
