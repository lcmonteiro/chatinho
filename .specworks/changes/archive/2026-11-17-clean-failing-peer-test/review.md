# Review: clean-failing-peer-test

Base: `origin/main`

## Findings

None.

## Changed files without tags

None: `specworks review` lists no untraced source or test files. The one changed file, `tests/frontends/test_mcp_frontend.py`, keeps its `@ac AC-FRONT-025.5` tag on `test_a_failing_peer_is_an_error`.

## Summary

The test now asks a local `_Failing` peer (`@connector("weather")`, `@require(HookAnswer)`) whose `answer` raises `RuntimeError("boom")`, which is the WHEN of AC-FRONT-025.5; the double construction and the patch through `session._peers()[1]` are gone, and its assertions (status `error`, `failed` in the text) are unchanged. The local peer follows the file's `_Echo`/`_Mute` style. No library code, spec, design or shared fake changed; the full suite passes (826 tests). Nothing sent back.
