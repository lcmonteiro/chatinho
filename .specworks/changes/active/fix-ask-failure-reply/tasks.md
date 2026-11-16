# Tasks: fix-ask-failure-reply

## 1. A failing answer is an error reply

- [x] 1.1 Confirm the API is unchanged: `ask` keeps its signature, no stubs needed (REQ-CORE-007, REQ-CORE-011); verify `specworks run typecheck`
- [ ] 1.2 [test] Rewrite the test tagged `@ac AC-CORE-007.5` so the failing peer's `ask` returns a `Reply` with status `error` naming the peer and `RuntimeError`, and the other ask its answer; verify it fails against today's code because `ask` raises
- [ ] 1.3 [test] Rewrite the test tagged `@ac AC-CORE-011.1` so an `ask` of a peer returning a string returns `error` naming `TypeError`, and the addressed say still gets an `error` reply; verify it fails because `ask` raises `TypeError`
- [ ] 1.4 [test] Add a test tagged `@ac AC-CORE-011.5`: a peer raising `RuntimeError("secret prompt")` is asked; the conversation holds one reply to the question from that peer, status `error`, `to` unset, naming `RuntimeError` and not `secret prompt`; verify it fails because nothing is posted today
- [ ] 1.5 [test] Keep the test tagged `@ac AC-CORE-011.4` (an addressed say) unchanged; verify it still passes
- [x] 1.6 [code] In `ChatSession._deliver`, post the error reply for every failing `answer` and let `_post` resolve a waiting ask, still re-raising for the log (REQ-CORE-007, REQ-CORE-011) tagged `@req REQ-CORE-007, REQ-CORE-011`; verify with `specworks run lint` and `specworks run typecheck`
- [x] 1.7 [code] Update `CLAUDE.md` (Three verbs; Attachments) to say an ask of a failing peer returns its `error` reply and a string returned by `answer` is such a failure (REQ-CORE-007, REQ-CORE-011); verify by reading the two sections

## Workflow follow-up

- The agents' `_asking` keeps its `try/except` for the `ask`'s own errors (unknown peer, the chat closing).
