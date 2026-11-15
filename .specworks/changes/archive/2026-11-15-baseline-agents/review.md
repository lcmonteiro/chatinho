# Review: baseline-agents

Base: `origin/main`

## Findings

None.

## Changed files without tags

- `docs/architecture.md`, `docs/diagrams/architecture-blocks.d2`, `docs/diagrams/architecture-blocks.svg`: the first architecture, written by the adoption before this change; documentation.
- `src/chatinho/docs/`, `src/chatinho/support/parts/keys/docs/` and `src/chatinho/support/parts/workspace/docs/` (`spec.md`, `requirements.md`, `design.md` and their diagrams): the living docs of `framework`, `keys` and `workspace-model`, written when their baselines closed; documentation.
- `.claude/skills/specworks-*/SKILL.md`, `.specworks/config.yml`: installed and written by the adoption before this change; configuration.

## Summary

Five source files of `agents`, its two test files and `tests/test_architecture.py` gained only `@req` and `@ac` comment lines: 11 requirements and 24 criteria, no new test and no code change. The spec was read against `peer.py`, `tools.py` and `workspace_backend.py` and nothing drifted. `basic.py`, `deep.py`, `graph.py` and `results.py` carry no tag yet: what they do in a chat is shown by the connectors' tests and is left to the baseline of `connectors`, as the proposal says. The other tagged files in the diff against `origin/main` belong to baselines already closed on this branch.
