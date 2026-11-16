# Review: fix-ask-failure-reply

Base: `origin/main`

## Findings

- [x] R1 **code-gap** REQ-CORE-007, REQ-CORE-011: the reference for the hooks still documents the old behaviour. The `Ask` protocol's docstring says `Raises: Exception: Whatever the peer's answer raised, when it failed` (`src/chatinho/hooks.py:89-90`), and `docs/SPEC.md` HookAsk says ask raises 'whatever the peer's `answer` raised if it failed' (`docs/SPEC.md:190-191`) and that a failing peer replies with ERROR only 'when nobody is awaiting it' (`docs/SPEC.md:209-210`). The proposal's Impact named CLAUDE.md but not these two.
  - **Proposal**: back to code: in `hooks.py` `Ask.__call__`, document that a failing peer's ask returns its `error` reply and make Raises list only the ask's own failures (`ValueError` for an id that is no peer, `RuntimeError` when the chat closes while it waits); in `docs/SPEC.md` HookAsk, replace the 'and whatever the peer's answer raised' clause the same way, and say a peer whose `answer` fails replies with `ReplyStatus.ERROR` whether or not an ask awaits it (HookAnswer may say a string returned is such a failure). No test or spec change.
  - **Decision**: back to code: update the `Ask` docstring (src/chatinho/hooks.py) and docs/SPEC.md HookAsk/HookAnswer to say a failing peer's ask returns its `error` reply, raising only `ValueError` (unknown id) and `RuntimeError` (chat closed); a string returned by `answer` is such a failure
  - done in code: Ask docstring (src/chatinho/hooks.py) now says a failing peer's ask returns its error reply and Raises lists only ValueError (unknown id) and RuntimeError (chat closed); docs/SPEC.md HookAsk and HookAnswer say the same, and that the error reply is posted whether or not an ask awaits
  - confirmed in review: confirmed in cycle 2: the Ask docstring (src/chatinho/hooks.py) raises only ValueError and RuntimeError and says a failing peer's ask returns its error reply; docs/SPEC.md HookAsk and HookAnswer say the same; suite passes (818)

## Changed files without tags

None: `specworks review` lists no untraced source or test. `CLAUDE.md` is documentation, updated under task 1.7; `docs/SPEC.md` is documentation, updated under R1 (`src/chatinho/hooks.py` already carries its `@req` tags).

## Summary

The suite passes (818) and the code does what REQ-CORE-007 and REQ-CORE-011 now say: `_deliver` posts the `error` reply for every failing `answer` through `_answered`, and `_post` resolves a waiting `ask` with it, as the design's Decision says; the tests of AC-CORE-007.5, AC-CORE-011.1 and AC-CORE-011.5 assert the THEN through `ask` and the conversation. One finding: the two other places that document `ask` (the `Ask` grant's docstring and `docs/SPEC.md`) still say it raises the peer's error; proposed back to code. No spec or design change.

Cycle 2: R1 carried out in the code half and confirmed (the `Ask` docstring and `docs/SPEC.md` HookAsk/HookAnswer now match REQ-CORE-007 and REQ-CORE-011); the suite passes (818). No new finding.
