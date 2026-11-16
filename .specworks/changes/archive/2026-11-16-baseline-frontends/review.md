# Review: baseline-frontends

Base: `origin/main`

## Findings

- [x] R1 **test-gap** Five criteria, written from their tests' names, said something their tests do not assert: AC-FRONT-019.6 (naming an instance), AC-FRONT-020.7 (the confirmation's text), AC-FRONT-015.4 (the double tap and Textual's chain count), AC-FRONT-011.1 (a bubble's width) and AC-FRONT-010.2 (serving until the person quits) (`tests/frontends/test_chat_frontend.py`)
  - **Decision**: spec updated (ADDED REQ-FRONT-010, REQ-FRONT-011, REQ-FRONT-015, REQ-FRONT-019, REQ-FRONT-020): each of the five now says what its test asserts. No test changed.
- [x] R2 **test-gap** Validate found two more criteria that said more than their tests check (V1, V2 in validation.md): AC-FRONT-025.6 claimed a peer answering with status `error` yields a tool error, but its test only has a peer that raises; AC-FRONT-020.11 claimed a failing helper is logged, but its test only checks that copying returns nothing (`tests/frontends/test_mcp_frontend.py`, `tests/frontends/test_clipboard.py`)
  - **Decision**: spec updated (ADDED REQ-FRONT-020, REQ-FRONT-025): both criteria reworded to what their tests check. No test changed, as the user chose for the same kind of finding in `baseline-connectors`; the two untested behaviours are noted for a later change.

## Changed files without tags

- `src/chatinho/connectors/docs/` (`spec.md`, `requirements.md`, `design.md` and its diagram): the living docs of `connectors`, written when its baseline closed on this branch; documentation.
- `.specworks/changes/archive/2026-11-15-baseline-connectors/`: that baseline's archived change.

## Summary

Six source files and the five test files of `frontends` gained only `@req` and `@ac` comment lines: 28 requirements and 171 criteria, one per test, no new test and no code change. The criteria were written from the tests' names; the assertions of all 150 terminal tests were then read against them, which corrected the five criteria above. The assertions of the MCP, clipboard and suggestion tests were not read in this review. The tagged files of `connectors` in the diff against `origin/main` belong to its baseline, already closed on this branch.
