# Proposal

## Why

A peer sometimes has something too rich for a chat bubble: an HTML chart, a small page, a CSV file. Today a message is only text, so the peer has nowhere to put it. This change lets a message carry **attachments** that its markdown text links to by a relative name, so every peer and presentation sees the attachment as part of the message. It also makes a later backend able to keep attachments and serve them to a browser.

## What Changes

- Add an `Attachment` value type: a name (one relative path segment such as `revenue.html`), a media type (such as `text/html`) and the content as bytes.
- `ChatMessage` gains an `attachments` field that defaults to empty, so every existing construction and every message without attachments behaves exactly as before.
- Every way of producing a message can attach:
  - `say(text, *, reply_to=None, attachments=())`
  - `ask(to, text, *, attachments=())`
  - `answer()` and a command's `execute()` may return a new `Reply(text, attachments)` instead of a string. Returning a string keeps working unchanged.
- **Only linked attachments travel.** The message text is markdown. An attachment is kept on the message only when the text links to its name with a relative markdown link or image (`[chart](revenue.html)`, `![plot](plot.png)`). Unlinked attachments are dropped before the message is posted, so no peer ever receives them.
- **A link to a missing attachment is an error.** If the text links to a relative name that isn't among the message's attachments, the message is rejected with `ValueError` and nothing is posted.
- The terminal presentation resolves relative links in a message against an optional attachment base URL: a link to `revenue.html` in message `msg-42` opens `<base>/m/msg-42/revenue.html`. With no base URL configured, clicking such a link shows a notice instead of opening a broken URL.
- `docs/SPEC.md`, the hook protocols and the README describe the new parameters and return type.
- Out of scope, and left to a later change: any backend that stores attachments or serves them over HTTP (including `DatabaseBackend`, which keeps storing text only), and attachments on command invocations (`/name args`), which stay plain command lines.

## Capabilities

### New Capabilities
- `message-attachments`: how a message carries attachments, which of them travel with it (only those its markdown text links to), how every verb and return value attaches them, how a missing link target is rejected, and how the terminal resolves attachment links to URLs.

### Modified Capabilities
<!-- None: openspec/specs/ is empty; existing behavior is documented in docs/SPEC.md, which this change updates. -->

## Impact

- `src/chatinho/chat_message.py`: `Attachment`, `Reply`, the `attachments` field, and the link-scanning rule (standard library only, since the core imports nothing else).
- `src/chatinho/chat_session.py`: `say`, `ask`, answer and command-result posting accept attachments and apply the link rule.
- `src/chatinho/chat_hooks.py`: the `Say` and `Ask` protocols, and the documented return types of `answer` and `execute`.
- `src/chatinho/chat_log.py`, `chat_app.py`, `chat_builder.py`: relative link handling and the optional attachment base URL.
- `src/chatinho/__init__.py`: exports `Attachment` and `Reply`.
- `docs/SPEC.md`, `README.md`, `CLAUDE.md`: the new signatures and the link rule.
- Compatibility: no breaking changes. Existing connectors, commands and backends that ignore attachments keep working. A peer that returns a string from `answer` or `execute` is unaffected.
