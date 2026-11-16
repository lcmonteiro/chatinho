# Validation: baseline-frontends

## Findings

<!-- One finding per failed blocking check, written by `specworks validate --write`,
plus any added with `specworks finding add ... --artifact validation`.
`- [ ] V<n>` while open, `- [x] V<n>` once validate confirmed it.
Write "None." when there are no findings. -->

- [x] V1 **test-gap** AC-FRONT-025.6 says a peer that answers with status `error`, or raises, yields a tool error, but its test (test_ask_a_peer_that_fails) only makes the peer raise; no test has a peer return Reply(status="error") (tests/frontends/test_mcp_frontend.py)
  - **Proposal**: back to review: make AC-FRONT-025.6 say what its test asserts (the asked peer raises), or have the test also cover a peer returning a Reply with status error
  - confirmed in validate: spec updated (ADDED REQ-FRONT-025): AC-FRONT-025.6 now covers only a peer whose answer raises, which is what its test checks; a peer returning status error has no test, noted as a gap for a later change, as the user chose for connectors
- [x] V2 **test-gap** AC-FRONT-020.11 says a helper that fails is logged and nothing is raised, but its test (test_a_helper_that_fails_is_logged_and_not_raised) asserts only that put returns None; nothing checks the log (tests/frontends/test_clipboard.py)
  - **Proposal**: back to review: make AC-FRONT-020.11 say what its test asserts (put returns None and raises nothing), or have the test also assert the failure is logged
  - confirmed in validate: spec updated (ADDED REQ-FRONT-020): AC-FRONT-020.11 now says copying raises nothing and reports no helper, which is what its test checks; that the failure is logged is noted as untested for a later change

## Summary

Verdict: PASS (0 critical, 1 warnings)

- Completeness 11/11
- Correctness 7/8
- Coherence 3/3

Warnings:
- the specs are the ones agreed when specify passed: REQ-FRONT-010 changed; REQ-FRONT-011 changed; REQ-FRONT-015 changed; REQ-FRONT-019 changed; REQ-FRONT-020 changed; REQ-FRONT-025 changed; if that is intended, `specworks start design --change baseline-frontends` re-checks specify and accepts them; the tests and code then follow the new specs
