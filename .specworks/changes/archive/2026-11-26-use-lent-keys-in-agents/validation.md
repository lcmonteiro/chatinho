# Validation: use-lent-keys-in-agents

## Findings

<!-- One finding per failed blocking check, written by `specworks validate --write`,
plus any added with `specworks finding add ... --artifact validation`.
`- [ ] V<n>` while open, `- [x] V<n>` once validate confirmed it.
Write "None." when there are no findings. -->

- [x] V1 **code-gap** the test suite passes (commands.test); $ uv run pytest -q (in ., exit 1); warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.; ........................................................................ [ 7%]; ........................................................................ [ 14%]; ........................................................................ [ 21%]; ........................................................................ [ 28%]; ........................................................................ [ 35%]; ........................................................................ [ 42%]; ........................................................................ [ 49%]; .F...................................................................... [ 56%]; ........................................................................ [ 63%]; ........................................................................ [ 70%]; ..........s............................................................. [ 77%]; ........................................................................ [ 84%]; ........................................................................ [ 91%]; ........................................................................ [ 98%]; .............. [100%]; =================================== FAILURES ===================================; __________________ test_a_slow_peer_does_not_freeze_the_input __________________; ; async def test_a_slow_peer_does_not_freeze_the_input():; app = await chat_frontend(connectors=[_LentaPeer(), _Lua()]); async with app.run_test() as pilot:; inp = app.query_one("#input-line", CommandInput); inp.text = "@lenta are you there?"; await pilot.press("enter"); inp.text = "meanwhile"; await pilot.press("enter"); await _wait_for(app, pilot, "meanwhile"); > assert "lenta: done" not in [m.text for m in app.messages]; E AssertionError: assert 'lenta: done' not in ['are you there?', 'meanwhile', 'lenta: done']; ; tests/frontends/test_chat_frontend.py:401: AssertionError; =========================== short test summary info ============================; FAILED tests/frontends/test_chat_frontend.py::test_a_slow_peer_does_not_freeze_the_input; 1 failed, 1020 passed, 1 skipped in 106.32s (0:01:46)
  - **Check**: tests_pass
  - **Proposal**: back to code: make the check pass
  - confirmed in validate: the check passes

## Summary

Verdict: PASS (0 critical, 0 warnings)

- Completeness 11/11
- Correctness 7/7
- Coherence 3/3
