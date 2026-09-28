# Design

## Context

See proposal.md for motivation and specs/message-attachments/spec.md for the required behavior. The current code shapes the approach in these ways:

- Every message is built inside `ChatSession`:
  - `say` and `ask` in `_say_for` and `_ask_for`
  - the command's result in `_invoke_for`
  - an answer's reply in `_deliver`

  Every message goes through `_post`.
- `answer` and `execute` return `Optional[str]`. `ask` waits on a future that `_post` resolves with `msg.text`.
- The terminal renders message bodies with Textual's `Markdown`, which already opens clicked links itself (with the system opener, for example `xdg-open`).

## Goals / Non-Goals

**Goals:**
- A message carries attachments, and every way of producing a message can attach them.
- No change for peers, commands, backends or the terminal that never use attachments.

**Non-Goals:**
- Any validation: link targets, names, unlinked attachments. That is the backend's job.
- Storing, serving or building URLs for attachments. That is a later backend change.
- Terminal changes. Links keep opening the way they do today.

## Decisions

### `Attachment` and `Reply` are frozen dataclasses in `chat_message.py`

```python
@dataclass(frozen=True)
class Attachment:
    name       : str
    media_type : str
    data       : bytes

@dataclass(frozen=True)
class Reply:
    text        : str
    attachments : Tuple[Attachment, ...] = ()
```

`ChatMessage` gains `attachments : Tuple[Attachment, ...] = ()` as its **last** field, so existing constructions still work. Tuples and frozen dataclasses keep one peer from changing what another receives, since every listener gets the same message object.

### One builder unwraps a `Reply`

`ChatSession._message` builds every message a peer produces: `say`, `ask`, the answer reply and the command result. It unwraps a `Reply` into text plus attachments and passes them through as a tuple. The invocation message (`/name args`) is built with no attachments.

### `ask` and `invoke` still return text

The future behind `ask` resolves with the reply's text, and `invoke` returns the result's text. An asker that wants the attachments reads the reply message from `context()` or takes it from `listen`. This keeps both backward compatible.

## Risks / Trade-offs

- [`DatabaseBackend` stores text only, so recalled messages have no attachments] → Storing them is the backend change's decision.
- [Attachment content travels through every listener's queue] → Fine for pages and small files. Large payloads are the backend's problem.
