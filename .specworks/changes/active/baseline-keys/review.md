# Review: baseline-keys

Base: `origin/main`

## Findings

None.

## Changed files without tags

- `docs/architecture.md`, `docs/diagrams/architecture-blocks.d2`, `docs/diagrams/architecture-blocks.svg`: the first architecture, written by the adoption before this change; documentation.
- `src/chatinho/docs/spec.md`, `requirements.md`, `design.md`, `src/chatinho/docs/diagrams/framework-blocks.d2`, `framework-blocks.svg`: the living docs of `framework`, written when `baseline-framework` closed; documentation.
- `.claude/skills/specworks-*/SKILL.md`, `.specworks/config.yml`: installed and written by the adoption before this change; configuration.

## Summary

The two source files and two test files of `keys` gained only `@req` and `@ac` comment lines: 12 requirements and 38 criteria, no new test and no code change. The spec was read against `sources.py` and `endpoint.py` (the candidates for the profiles file, a command run without a shell) and nothing drifted. The other tagged files in the diff against `origin/main` belong to `baseline-framework`, already closed on this branch.
