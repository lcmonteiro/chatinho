# Review: baseline-workspaces

Base: `origin/main`

## Findings

None.

## Changed files without tags

- The living docs of `connectors`, `frontends`, `backends`, `commands` and `routers` under `src/chatinho/<capability>/docs/` (`spec.md`, `requirements.md`, `design.md` and their diagrams), and their archived changes under `.specworks/changes/archive/`: written by the baselines closed on this branch; documentation.

## Summary

`git.py` and its test file gained only `@req` and `@ac` comment lines: 5 requirements and 24 criteria, no new test and no code change. Every test's assertions and the provider's methods were read before the criteria were written. The tagged files of the other baselines in the diff against `origin/main` belong to baselines already closed on this branch.
