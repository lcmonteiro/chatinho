# Proposal

## Why

`add-message-attachments` put attachments on `ChatMessage`, so every listener's queue, the conversation context and the archive carry the bytes. But the app layer only needs the text. Storing attachments, touching the file system and turning a name into something a browser can open are all the backend's job. Today nothing can open a relative link such as `[chart](revenue.html)` at all, because nothing knows where `revenue.html` is.

## What Changes

- **BREAKING**: `ChatMessage` carries text only again. The `attachments` field is removed, so listeners, `context()` and the archive never see attachment bytes.
- Peers hand attachments over exactly as before: `say(..., attachments=)`, `ask(..., attachments=)`, and an `answer` or `execute` that returns `Reply(text, attachments)`. The session now passes them straight to the backend, keyed by the new message's id, before the text is posted.
- Three new hooks, taking chatinho from 11 to 14:
  - `HookKeep` demands `keep(msg_id, attachments)`: the backend stores a message's attachments.
  - `HookLink` demands `link(msg_id, name) -> Optional[str]`: the backend returns a link a browser can open, or `None`.
  - `HookLocate` grants `locate(msg_id, name) -> Optional[str]` to any peer. The session routes it to the backend's `link`.
- Without a backend that keeps attachments, they are dropped and `locate` returns `None`.
- The terminal opens a relative link in a message by calling `locate(message id, name)`. It opens the returned link, or shows "Not found" when there is none. Absolute links open as they do today.
- `DatabaseBackend` implements `keep` and `link`. It stores attachments in its database and writes a file only when someone asks for a link, returning a `file://` URI. `forget` drops the attachments of the messages it forgets.
- Out of scope: serving attachments over HTTP, validating attachments or links, and size limits.

## Capabilities

### New Capabilities
<!-- None: the behavior belongs to the existing message-attachments capability. -->

### Modified Capabilities
- `message-attachments`: attachments no longer ride on messages. They go to the backend, which keeps them and links them on request, any peer can locate them, and the terminal opens relative links through that lookup.

## Impact

- `src/chatinho/chat_message.py`: remove `ChatMessage.attachments`. `Attachment` and `Reply` stay.
- `src/chatinho/chat_session.py`: hand attachments to the `keep` backend before posting, and route the `locate` grant to the `link` backend.
- `src/chatinho/chat_hooks.py`, `src/chatinho/__init__.py`: `HookKeep`, `HookLink`, `HookLocate` and a `Locate` protocol.
- `src/chatinho/chat_app.py`, `src/chatinho/chat_log.py`: the terminal declares `HookLocate` and opens relative links through it.
- `src/chatinho/backends/database.py`: attachment storage, `keep`, `link`, a file cache that is cleaned at shutdown, and `forget` covering attachments.
- `docs/SPEC.md` (the hook table and sections, checked by `tests/test_architecture.py`), `README.md`, `CLAUDE.md`.
- Tests: `tests/test_attachments.py` is rewritten for the new flow, and the terminal and `DatabaseBackend` get new tests.
- Compatibility: code that read `msg.attachments` must use `locate` instead. The peer-facing API (`say`/`ask` attachments, `Reply`) is unchanged.
