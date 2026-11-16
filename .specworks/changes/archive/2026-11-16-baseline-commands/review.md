# Review: baseline-commands

Base: `origin/main`

## Findings

None.

## Changed files without tags

- `src/chatinho/connectors/docs/`, `src/chatinho/frontends/docs/` and `src/chatinho/backends/docs/` (`spec.md`, `requirements.md`, `design.md` and their diagrams), and their archived changes under `.specworks/changes/archive/`: the living docs of the baselines closed on this branch; documentation.

## Summary

`workspace.py`, `help.py` and the `/ws` test file gained only `@req` and `@ac` comment lines: 5 requirements and 10 criteria, no new test and no code change. Every test's assertions and `WorkspaceCommand.execute` were read before the criteria were written. The tagged files of `connectors`, `frontends` and `backends` in the diff against `origin/main` belong to their baselines, already closed on this branch.
