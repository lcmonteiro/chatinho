# Proposal

## Why

A peer sometimes has something too rich for a chat bubble: an HTML chart, a small page, a CSV file. Today a message is only text, so the peer has nowhere to put it. This change lets a message carry **attachments** that its markdown text can link to by name, so every peer and presentation receives them as part of the message. A backend can then check, keep and serve them.

## What Changes

- Add an `Attachment` value type: a name (what the text links to, such as `revenue.html`), a media type (such as `text/html`) and the content as bytes.
- `ChatMessage` gains an `attachments` field that defaults to empty, so every existing construction and every message without attachments behaves exactly as before.
- Every way of producing a message can attach:
  - `say(text, *, reply_to=None, attachments=())`
  - `ask(to, text, *, attachments=())`
  - `answer()` and a command's `execute()` may return a new `Reply(text, attachments)` instead of a string. Returning a string keeps working unchanged.
- The session passes attachments through as given. It doesn't check links, drop anything or validate names.
- Links in a message stay as they are today: the terminal renders them and opens them on click.
- Out of scope, and the responsibility of a later backend change: validating attachments and links, deciding what to keep, storing them and serving them to a browser. Command invocations (`/name args`) carry no attachments.

## Capabilities

### New Capabilities
- `message-attachments`: how a message carries attachments, and how every verb and return value attaches them.

### Modified Capabilities
<!-- None: openspec/specs/ is empty; existing behavior is documented in docs/SPEC.md, which this change updates. -->

## Impact

- `src/chatinho/chat_message.py`: `Attachment`, `Reply` and the `attachments` field.
- `src/chatinho/chat_session.py`: `say`, `ask`, and answer and command-result posting carry attachments.
- `src/chatinho/chat_hooks.py`: the `Say` and `Ask` protocols, and the documented return types of `answer` and `execute`.
- `src/chatinho/__init__.py`: exports `Attachment` and `Reply`.
- `docs/SPEC.md`, `README.md`, `CLAUDE.md`: the new signatures.
- Compatibility: no breaking changes. The terminal is unchanged.
