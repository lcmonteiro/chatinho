# Refinement: fix-ask-failure-reply

## Problem

When a peer's `answer` raises, what happens depends on how the question was put. A say addressed to the peer gets a reply with status `error` in the conversation. An `ask` waiting on the peer raises the peer's own exception in the asker, and no message is posted: the conversation keeps a question with no reply, and nobody but the asker learns that it failed. The baseline of `framework` found it.

## Outcomes

- An `ask` of a peer whose `answer` raises returns a `Reply` with status `error`, as it already does for an answer that says `error` and for a question past the nesting limit.
- That error reply is in the conversation, replying to the question and addressed to nobody, so listeners, the archive and `context()` show that the question failed.

## Context

**Observed:**
- `src/chatinho/session.py`, `ChatSession._deliver`: on an exception from `answer`, a waiting ask gets `set_exception(exc)`; only with no ask waiting is the `"<peer> failed: <error type>"` reply posted. The comment there says this is deliberate.
- `_checked` turns an `answer` that returns anything but a `Reply` or `None` (a string most often) into `TypeError`, inside the same `try`, so it follows the same path.
- `src/chatinho/support/kits/agent/tools.py`, `_asking` (the agents' `ask_<peer>` tools, REQ-CONN-016): the only caller of `ask` in the library. It catches any exception and builds by hand the same `Reply("<peer> failed: <error type>", status=error)` the session posts for a say.
- `tests/framework/test_chat_session.py::test_a_peer_that_raises_does_not_take_the_chat_down` expects the `RuntimeError` in the asker; `tests/framework/test_answer_details.py::test_an_answer_must_be_a_reply` expects `TypeError` from an `ask` of a peer that returns a string.
- `tests/framework/test_message_delivery.py::test_an_error_reply_is_addressed_to_nobody` shows the error reply for an addressed say.
- `CLAUDE.md` ("Three verbs"): `ask` returns the answer's `Reply`, status and all, "rather than the session turning one of them into an exception"; "Attachments go to the backend" says a string raises `TypeError`.
- The `framework` living spec (`src/chatinho/docs/spec.md`) records the current behaviour: REQ-CORE-007 ("the waiting `ask` MUST raise that error", AC-CORE-007.5) and REQ-CORE-011 (AC-CORE-011.1, AC-CORE-011.4).
- Other failures of an `ask` are not the asked peer's: an unknown id raises `ValueError`, and `close()` fails every waiting ask with `RuntimeError("the chat closed")`. A question past the nesting limit already gets an `error` reply.

**Assumed:**
- A model reads an `error` reply from `ask_<peer>` as well as it reads the one `_asking` builds today, since the text is the same.

## Constraints

- [hard] The chat carries on when a peer fails, as today.
- [hard] The error reply names only the exception's type, never its message: an exception may echo a prompt.
- [soft] No caller should need to catch another peer's exception types.

## Options

**A. Every failure of `answer` is an `error` reply (chosen).** In `_deliver`, a failing `answer` (an exception, or `TypeError` for a non-`Reply`) posts the `"<peer> failed: <type>"` reply whether or not an ask waits; the waiting ask resolves on it like on any answer and returns `Reply(status=error)`. The failure is still logged by `_delivery`.
- Meets both outcomes. One rule for a say and an ask.
- Con: a peer with a bug (returning a string) no longer fails loudly in the asker; it shows as `"x failed: TypeError"` in the conversation and in the log.
- Effort S. Touches `framework` (REQ-CORE-007, REQ-CORE-011), two framework tests, CLAUDE.md.

**B. Only exceptions become a reply; a broken contract still raises.** As A, but `TypeError` from `_checked` keeps raising in the asker.
- Meets both outcomes for exceptions only. Two rules, and a real `TypeError` raised inside `answer` cannot be told from the contract's.
- Effort S.

**C. Do nothing; document the current behaviour.**
- Fails both outcomes. `_asking` keeps duplicating the session's reply, and the archive keeps a question with no answer.
- Effort XS.

## Recommendation

Option A, agreed with the maintainer: one rule for every question asked of a peer, the asker never catches another peer's exception, and the failure stays visible in the log.

In scope: `_deliver`, the two tests that expect the exception, the CLAUDE.md wording, REQ-CORE-007 and REQ-CORE-011. Out of scope: `ValueError` for an unknown id, `RuntimeError` when the chat closes, the nesting limit. To decide in specify: whether `_asking` drops its now partly redundant `try/except` (it still covers the `ask`'s own exceptions, so it may stay).

## Open Questions

None. Answered: a string returned by `answer` follows the same rule (option A).

## Candidate Capabilities

- `framework`: modified - REQ-CORE-007 and REQ-CORE-011 change for a failing `answer`.
- `connectors`: possibly modified - REQ-CONN-016, if `_asking` changes.
