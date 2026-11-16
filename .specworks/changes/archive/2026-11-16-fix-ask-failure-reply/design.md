# Design: fix-ask-failure-reply

## Context

See `proposal.md`. Today `ChatSession._deliver` (`src/chatinho/session.py`) pops the waiting future and calls `set_exception` when an `ask` waits; only otherwise does it post the `"<peer> failed: <type>"` reply. `_post` already resolves a waiting ask from any reply to the question by the peer it is addressed to (REQ-CORE-008).

## Goals / Non-Goals

- Goal: one path for a failing `answer`, whoever waits on it (REQ-CORE-007, REQ-CORE-011).
- Non-goal: changing the error text, the logging in `_delivery`, or the agents' `_asking`.

## Decisions

- **The error reply resolves the ask through `_post`.** `_deliver` no longer touches `_pending`: on a failure it posts the error reply in the asked peer's name (`frm=at`, `reply_to=msg.id`, `to=None`, status `error`), and `_post` resolves the waiting `ask` the way it resolves any answer. Alternative: keep popping the future and `set_result` with the posted message; rejected, it is a second resolution path that REQ-CORE-008 would have to be checked against twice. (REQ-CORE-007, REQ-CORE-011)
- **The text stays `"<peer> failed: <exception type>"`.** It already names only the type, so no prompt echoed in an exception's message leaks into the conversation or the archive. (REQ-CORE-011)
- **`_deliver` still re-raises** after posting, so `_delivery` keeps logging the failure with its traceback. The re-raise happens inside the delivery task, never in the asker.

## Interfaces

None. `ask(to, text, *, attachments=()) -> Reply` keeps its signature; only what it does for a failing peer changes (it returns `Reply(status=error)` instead of raising).

## Diagrams

No structural change.

## Risks / Trade-offs

- [a consumer catching the peer's exception from `ask`] -> the exception no longer arrives; it reads `reply.status` instead. Stated as BREAKING in the proposal and in `CLAUDE.md`.
- [a peer bug (returning a string) is quieter] -> it is still logged with its traceback, and the reply names `TypeError`.

## Open Questions

None.
