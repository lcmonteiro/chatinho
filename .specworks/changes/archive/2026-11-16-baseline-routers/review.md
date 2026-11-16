# Review: baseline-routers

Base: `origin/main`

## Findings

None.

## Changed files without tags

- `src/chatinho/connectors/docs/`, `src/chatinho/frontends/docs/`, `src/chatinho/backends/docs/` and `src/chatinho/commands/docs/` (`spec.md`, `requirements.md`, `design.md` and their diagrams), and their archived changes under `.specworks/changes/archive/`: the living docs of the baselines closed on this branch; documentation.

## Summary

`simple.py`, `builder.py`, the routing code of `session.py` and the routing test file gained only `@req` and `@ac` comment lines: 6 requirements and 27 criteria, no new test and no code change. Every test's assertions, `SimpleRouter.route` and `ChatSession._routed` were read before the criteria were written. REQ-ROUTE-001 to REQ-ROUTE-003 are tagged in `session.py`, where the session consults its router. The tagged files of the other baselines in the diff against `origin/main` belong to baselines already closed on this branch.
