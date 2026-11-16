# Proposal: fix-ask-failure-reply

## Why

When the asked peer's `answer` fails, an `ask` raises that peer's own exception and nothing is posted, while a say addressed to the same peer gets an `error` reply. The conversation keeps a question with no answer, and every caller of `ask` has to catch another peer's exceptions (the agents' `ask_<peer>` tools already rebuild the error reply by hand). Found by the `framework` baseline.

## What Changes

- A failing `answer` (it raises, or returns anything but a `Reply` or `None`) is always answered by the session with a reply of status `error`, posted in the asked peer's name, replying to the question and addressed to nobody, whether or not an `ask` waits on it.
- A waiting `ask` returns that reply (`Reply(status=error)`, text `<peer> failed: <exception type>`) instead of raising. **BREAKING** for a caller that caught the exception from `ask`; inside the library only `_asking` did, and its result does not change.
- The failure is still logged, as today.
- `CLAUDE.md` describes the new rule (Three verbs; Attachments).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `framework`: REQ-CORE-007 (an ask of a failing peer returns its error reply) and REQ-CORE-011 (the error reply is posted whether or not an ask waits; a string returned is one such failure).

## Related requirements

- REQ-CORE-007 modified.
- REQ-CORE-011 modified.
- REQ-CORE-008 left: the error reply is posted in the asked peer's name, so only it resolves the ask, as the rule says.
- REQ-CORE-015 left: a question past the nesting limit already gets an `error` reply.
- REQ-CORE-016 left: an ask still waiting when the chat closes still fails; that is not the asked peer's failure.
- REQ-CORE-009 left: an addressed say already gets the error reply; unchanged.
- REQ-CONN-016 left: an `ask_` tool still gives an `error` reply naming the peer and the kind of failure; the reply now comes from the session, and the tool's own catch stays for the `ask`'s own errors (unknown peer, the chat closing).
- REQ-FRONT-025 left: McpFrontend asks with an addressed say, which already gets the error reply and yields a tool error.
- REQ-CONN-005, REQ-AGENT-007 left: they are about a connector's or an agent's own failures, not the session's.
- The other matches of `ask`, `failed` and `TypeError` (keys, workspaces, routers, backends) are unrelated to an answer failing.

## Impact

- `src/chatinho/session.py`: `ChatSession._deliver`.
- Tests: `tests/framework/test_chat_session.py::test_a_peer_that_raises_does_not_take_the_chat_down`, `tests/framework/test_answer_details.py::test_an_answer_must_be_a_reply`.
- `CLAUDE.md`.
- Public behaviour of `ask` for consumers that caught a peer's exception.

## Out of Scope

- `ValueError` for an ask of an id that is no peer.
- `RuntimeError("the chat closed")` for an ask still waiting at `close()`.
- The nesting limit, which already answers with `error`.
- Simplifying the agents' `_asking` tool: its catch still covers the `ask`'s own errors, so it stays as it is.
