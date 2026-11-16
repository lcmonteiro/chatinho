# Review: fix-ask-failure-reply

Base: `origin/main`

## Findings

- [ ] R1 **code-gap** REQ-CORE-007, REQ-CORE-011: the reference for the hooks still documents the old behaviour. The `Ask` protocol's docstring says `Raises: Exception: Whatever the peer's answer raised, when it failed` (`src/chatinho/hooks.py:89-90`), and `docs/SPEC.md` HookAsk says ask raises 'whatever the peer's `answer` raised if it failed' (`docs/SPEC.md:190-191`) and that a failing peer replies with ERROR only 'when nobody is awaiting it' (`docs/SPEC.md:209-210`). The proposal's Impact named CLAUDE.md but not these two.
  - **Proposal**: back to code: in `hooks.py` `Ask.__call__`, document that a failing peer's ask returns its `error` reply and make Raises list only the ask's own failures (`ValueError` for an id that is no peer, `RuntimeError` when the chat closes while it waits); in `docs/SPEC.md` HookAsk, replace the 'and whatever the peer's answer raised' clause the same way, and say a peer whose `answer` fails replies with `ReplyStatus.ERROR` whether or not an ask awaits it (HookAnswer may say a string returned is such a failure). No test or spec change.

## Changed files without tags

None: `specworks review` lists no untraced source or test. `CLAUDE.md` is documentation, updated under task 1.7.

## Summary

The suite passes (818) and the code does what REQ-CORE-007 and REQ-CORE-011 now say: `_deliver` posts the `error` reply for every failing `answer` through `_answered`, and `_post` resolves a waiting `ask` with it, as the design's Decision says; the tests of AC-CORE-007.5, AC-CORE-011.1 and AC-CORE-011.5 assert the THEN through `ask` and the conversation. One finding: the two other places that document `ask` (the `Ask` grant's docstring and `docs/SPEC.md`) still say it raises the peer's error; proposed back to code. No spec or design change.
