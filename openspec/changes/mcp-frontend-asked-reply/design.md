# Design

## Context

- **How a client's question flows.** `McpFrontend._asked` says the client's text with `say(text, to=at, credentials=…)` and keeps the open call in `_open`, keyed by the question's message id. `listen` hears every message. Today it ends the call on the first message whose `reply_to` names an open question, whoever said it.
- **Who was asked is already recorded.** The session sets `asked_of` on every message it posts. A say with `to` gets `asked_of == to`, so the question in the conversation already carries the peer the client asked.
- **Who replies is recorded too.** A reply's `frm` is its sender. The session posts the answer `answer` returned, the error reply when `answer` raises, and the "too many nested asks" reply all with `frm` set to the asked peer. A late answer (an `answer` that returned `None` and said the reply later) is a say from that peer, so its `frm` is the peer as well.
- **The reviewer's constraint.** In [lcmonteiro/chatinho#42](https://github.com/lcmonteiro/chatinho/pull/42), keeping the asked peer's id on `_Message` was reverted. This design keeps nothing new per question.

## Goals / Non-Goals

**Goals:**

- A client's call ends only with the asked peer's reply.
- No new per-question state in `McpFrontend`.

**Non-Goals:**

- Changing how the session routes or resolves its own `ask` (it already applies this rule).
- Changing `McpConnector`, the client side, which asks a remote session and is unaffected.
- Making `context()` faster. See Risks.

## Decisions

### 1. Look the question up in the conversation

`McpFrontend` declares `HookContext` and annotates `context : Context`. In `listen`, after the existing guards (a `reply_to` naming an open, unfinished call), it finds the question with `next((m for m in self.context() if m.id == msg.reply_to), None)` and compares `msg.frm` with the question's `asked_of`. A mismatch returns without touching the call.

- **Why `asked_of` and not `to`:** they are equal for this message, which is a say with `to`. `asked_of` is the field the session defines as "whose answer is called", which is the same rule the session's own `ask` resolution uses.
- **Alternative rejected:** keeping the peer id on `_Message`. It was reverted at review.
- **Alternative rejected:** `Query(thread=msg.reply_to)` to narrow the read. It still scans the conversation inside the session, and it is less direct than finding one message by id.

### 2. A question that can't be found takes the first reply

When `forget()` drops the question while its call is open, the lookup finds nothing. The call then ends with the reply in hand, which is today's behaviour, rather than waiting until the client gives up. That needs `forget()` running in the middle of an open MCP call, which is rare enough that reverting to the old rule is the proportionate answer.

## Risks / Trade-offs

- [`context()` copies the whole conversation, so each reply to an open question costs a scan] → It runs only for replies whose `reply_to` names an open call, which is at most a handful per question. The conversation in memory is bounded by `recall` plus this session's messages. The same cost already exists wherever `ChatLog` uses `_find`.
- [Declaring `HookContext` lets `McpFrontend` read the conversation] → It speaks for every client and already hears every message through `listen`, so reading it grants nothing new.
- [Removing the first-reply shortcut could leave a call waiting if the asked peer never replies] → Unchanged from today: the call waits until the asked peer replies, the client ends its call (which `_close` already handles), or the session closes (`shutdown` closes every open call).
