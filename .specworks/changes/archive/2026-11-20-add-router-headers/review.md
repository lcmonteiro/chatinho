# Review: add-router-headers

Base: `origin/main`

## Findings

None.

Read both ways against REQ-ROUTE-012 and design.md: `headers` is a keyword of
`LLMRouter.__init__` (`src/chatinho/routers/llm.py`), validated and copied by
`_checked_headers` (a non-mapping, a non-string name or value, and
`authorization` in any case raise `ValueError` naming the header, never a
value), kept as the private `_headers` (None when empty) and passed as
`default_headers` to both clients, the lent key's in `_choose` and its own in
`_own_client`. `__repr__` and the warnings are unchanged and show no value.
AC-ROUTE-012.1 to .7 each have a test that checks its THEN; .3 passes on the
old code by design (no headers means today's behaviour). The SDK merging
`default_headers` over its own `Authorization`, the reason for refusing it,
was checked on a real `AsyncOpenAI` (no request made).

## Changed files without tags

- `tests/fakes/llm.py`: test double; `FakeOpenAI` now records the `default_headers` a client is built with, read by the AC-ROUTE-012 tests.

## Summary

No drift between code, spec and design. The code adds `headers` to
`LLMRouter` for both key paths, with build-time validation; seven acceptance
tests cover it, and the full suite passes (970 passed, 1 skipped).
