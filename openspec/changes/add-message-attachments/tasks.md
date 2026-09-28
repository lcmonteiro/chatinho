# Tasks

## 1. Message model and link rule (core, standard library only)

- [x] 1.1 In `src/chatinho/chat_message.py`, add frozen dataclasses `Attachment(name, media_type, data: bytes)` and `Reply(text, attachments=())`, and add `attachments : Tuple[Attachment, ...] = ()` as the last field of `ChatMessage`. Verify existing `tests/test_message_store.py` and `tests/test_chat_session.py` still pass unchanged.
- [x] 1.2 Add `attached(text, attachments)`. It validates names (one segment, no `/` or `\`, not `.`/`..`, not empty, unique), finds relative inline link and image targets after removing fenced blocks and inline code spans, strips `./`, unquotes, raises `ValueError` naming any missing target, and returns only the linked attachments in their original order. Verify with a new `tests/test_attachments.py` covering: linked kept, image kept, unlinked dropped, missing target raises, invalid and duplicate names raise, absolute/`//`/`/`/`#`/query targets ignored, links inside fences and code spans ignored, `<...>` targets and titles, percent-encoded names.
- [x] 1.3 Add `attachment_url(base, msg, href)`, returning `<base>/m/<msg.id>/<quoted name>` for a relative link to one of `msg`'s attachments, and `None` without a base or a matching attachment. Verify with tests in `tests/test_attachments.py`, including a trailing `/` on the base and a name that needs quoting.

## 2. Session: every verb attaches

- [x] 2.1 In `src/chatinho/chat_session.py`, add one message builder that applies `attached()`. Use it for `say(text, *, reply_to=None, attachments=())` and `ask(to, text, *, attachments=())`, so a rejected message raises before `_post`. Verify with session tests: listeners receive only linked attachments, and a missing target raises from `say`/`ask` with nothing stored (the context is unchanged).
- [x] 2.2 Accept `Optional[Union[str, Reply]]` from `answer` (in `_deliver`) and from `execute` (in `_invoke_for`). Build the posted message through the same builder, resolve `ask`'s future with the reply text, and have `invoke` return the text. Verify with tests: answer with a `Reply` carries attachments and `ask` returns the text; a command `Reply` carries attachments and `invoke` returns the text; string returns are unchanged; an answer linking a missing name posts nothing and the chat keeps running; a command doing the same raises from `invoke`.
- [x] 2.3 Keep the invocation message (`/name args`) free of attachments, and verify with a test that it posts with an empty attachment list.

## 3. Hooks, exports and docs

- [x] 3.1 Update the `Say` and `Ask` protocols in `src/chatinho/chat_hooks.py` to take `attachments`, and document the widened `answer`/`execute` return type. Export `Attachment` and `Reply` from `src/chatinho/__init__.py` (listed in `__all__`). Verify `mypy src/chatinho` is clean and `from chatinho import Attachment, Reply` works.
- [x] 3.2 Update `docs/SPEC.md` (the `HookSay`, `HookAsk`, `HookAnswer`, `HookExecute` sections and a short "Attachments" subsection on the link rule and URL scheme), `README.md` (a usage example) and `CLAUDE.md` (the layout line and the rule). Verify `pytest tests/test_architecture.py` still passes, since it checks `docs/SPEC.md` against the hooks.

## 4. Terminal

- [x] 4.1 In `src/chatinho/chat_log.py`, create the message body `Markdown` with `open_links=False` and handle its link-clicked message per bubble:
  - absolute link: open with `app.open_url`
  - attachment link: open `attachment_url(...)`
  - otherwise: notify "No attachment server is configured" or "Attachment not available"

  Verify with a mounted test in `tests/test_chat_app.py` that patches `open_url` and checks each branch.
- [x] 4.2 Add `attachment_url : Optional[str] = None` to `ChatApp` and `build_chat` (documented in their docstrings) and pass it to the log. Verify with a test that `build_chat(attachment_url=...)` reaches the log, and that `test_we_never_shadow_a_textual_method` and `test_a_grant_never_shadows_a_textual_method` still pass.

## 5. Verification

- [x] 5.1 Run the three CI checks, `ruff check src tests examples`, `mypy src/chatinho` and `pytest -q`, and verify all pass
- [x] 5.2 Run `openspec validate --all --strict --no-interactive` and verify it passes
