# Proposal: remove-openspec

## Why

Every capability of chatinho has a living spec in specworks, so OpenSpec now describes the same library a second time, in specs nobody updates.

## What Changes

- Delete `openspec/`, the OpenSpec skills (`.claude/skills/openspec-*`), the `/opsx` commands (`.claude/commands/opsx/`) and the `openspec` CI job.
- Drop the OpenSpec CLI from `.claude/hooks/session-start.sh` and `OPENSPEC_TELEMETRY` from `.claude/settings.json`; the hook keeps building `.venv` in a cloud session.
- Rewrite the workflow parts of `CLAUDE.md` and `README.md` for specworks, and point five test docstrings at their capability's living spec.
- No behaviour change.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None: tooling and docs only.

## Related requirements

None.

## Impact

Tooling, CI and docs. No source code, API, data or dependency changes; five test docstrings change.

## Out of Scope

- `docs/SPEC.md`, the hooks reference, which a test checks against the code: it stays.
