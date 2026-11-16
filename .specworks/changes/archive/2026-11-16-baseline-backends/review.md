# Review: baseline-backends

Base: `origin/main`

## Findings

- [x] R1 **spec-gap** REQ-BACK-006 (a session without a backend) had no code in `backends`: what a session with no backend does is decided in `src/chatinho/session.py`, and REQ-CORE-020 already records it (`tests/backends/test_database_backend.py`)
  - **Decision**: spec updated (ADDED REQ-BACK-006 dropped before close): the requirement is left out of this delta and its ID not used; the test carries `@ac AC-CORE-020.1` instead.

## Changed files without tags

- `src/chatinho/frontends/docs/` (`spec.md`, `requirements.md`, `design.md` and its diagram) and `.specworks/changes/archive/2026-11-16-baseline-frontends/`: the living docs and the archived change of `frontends`, closed on this branch; documentation.
- `src/chatinho/connectors/docs/` and `.specworks/changes/archive/2026-11-15-baseline-connectors/`: the same for `connectors`.

## Summary

`database.py` and its test file gained only `@req` and `@ac` comment lines: 7 requirements and 28 criteria of `backends`, plus one test tagged with a `framework` criterion. No new test and no code change. Every test's assertions were read before the criteria were written. The tagged files of `connectors` and `frontends` in the diff against `origin/main` belong to their baselines, already closed on this branch.
