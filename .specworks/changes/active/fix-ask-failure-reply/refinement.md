# Refinement: fix-ask-failure-reply

## Problem

When a peer's `answer` raises, what happens depends on how the question was put. A say addressed to the peer gets a reply with status `error` in the conversation. An `ask` waiting on the peer raises the peer's own exception in the asker, and no message is posted: the conversation keeps a question with no reply, and nobody but the asker learns that it failed. The baseline of `framework` found it.

## Outcomes

- An `ask` of a peer whose `answer` raises returns a `Reply` with status `error`, as it already does for an answer that says `error` and for a question past the nesting limit.
- That error reply is in the conversation, replying to the question and addressed to nobody, so listeners, the archive and `context()` show that the question failed.

## Context

**Observed:**
- `src/chatinho/session.py`, `ChatSession._deliver`: on an exception from `answer`, a waiting ask gets `set_exception(exc)`; only with no ask waiting is the `"<peer> failed: <error type>"` reply posted. The comment there says this is deliberate.
- `tests/framework/test_chat_session.py::test_a_peer_that_raises_does_not_take_the_chat_down` expects the `RuntimeError` in the asker; `tests/framework/test_answer_details.py::test_an_answer_must_be_a_reply` expects `TypeError` from an `ask` of a peer that returns a string.
- `tests/framework/test_message_delivery.py::test_an_error_reply_is_addressed_to_nobody` shows the error reply for an addressed say.
- `CLAUDE.md` ("Three verbs"): `ask` returns the answer's `Reply`, status and all, "rather than the session turning one of them into an exception".
- `openspec/specs/message-delivery` counts "the `ERROR` reply when its `answer` raises" as the asked peer's reply.
- The baseline records the current behaviour as AC-CORE-007.5 and AC-CORE-011.4.

**Assumed:**
- The agent connectors' `ask_<peer>` tools would read an `error` reply better than an exception from another peer; not checked.

## Constraints

- [hard] The chat carries on when a peer fails, as today.
- [soft] No caller should need to catch another peer's exception types.

## Options

Pending.

## Recommendation

Pending.

## Open Questions

- Should a string returned by `answer` (today `TypeError` in the asker) follow the same rule? (who can answer: the maintainer)

## Candidate Capabilities

- `framework`: modified - REQ-CORE-007 and REQ-CORE-011 change for a failing `answer`.
