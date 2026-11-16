# Validation: baseline-frontends

## Findings

<!-- One finding per failed blocking check, written by `specworks validate --write`,
plus any added with `specworks finding add ... --artifact validation`.
`- [ ] V<n>` while open, `- [x] V<n>` once validate confirmed it.
Write "None." when there are no findings. -->

- [ ] V1 **test-gap** AC-FRONT-025.6 says a peer that answers with status `error`, or raises, yields a tool error, but its test (test_ask_a_peer_that_fails) only makes the peer raise; no test has a peer return Reply(status="error") (tests/frontends/test_mcp_frontend.py)
  - **Proposal**: back to review: make AC-FRONT-025.6 say what its test asserts (the asked peer raises), or have the test also cover a peer returning a Reply with status error
- [ ] V2 **test-gap** AC-FRONT-020.11 says a helper that fails is logged and nothing is raised, but its test (test_a_helper_that_fails_is_logged_and_not_raised) asserts only that put returns None; nothing checks the log (tests/frontends/test_clipboard.py)
  - **Proposal**: back to review: make AC-FRONT-020.11 say what its test asserts (put returns None and raises nothing), or have the test also assert the failure is logged

## Summary

Verdict: FAIL (1 critical, 1 warnings)

- Completeness 10/11
- Correctness 7/8
- Coherence 3/3

Warnings:
- the specs are the ones agreed when specify passed: REQ-FRONT-010 changed; REQ-FRONT-011 changed; REQ-FRONT-015 changed; REQ-FRONT-019 changed; REQ-FRONT-020 changed; if that is intended, `specworks start design --change baseline-frontends` re-checks specify and accepts them; the tests and code then follow the new specs
