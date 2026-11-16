# Review: remove-openspec

Base: `origin/main`

## Findings

None.

## Changed files without tags

- `openspec/` (every file under it): deleted; OpenSpec's specs and its archive of changes, replaced by the living specs of the ten capabilities.
- `.claude/skills/openspec-*/SKILL.md` and `.claude/commands/opsx/*.md`: deleted; OpenSpec's skills and commands.
- `.github/workflows/tests.yml`, `.claude/hooks/session-start.sh`, `.claude/settings.json`: the `openspec` CI job, the CLI install and its telemetry variable removed; tooling.
- `README.md`, `CLAUDE.md`: the workflow described for specworks instead; documentation.

## Summary

OpenSpec is gone: its folder, skills, commands, CI job, CLI install and telemetry variable. `README.md` and `CLAUDE.md` describe the specworks workflow, and five test docstrings point at their capability's living spec instead of an OpenSpec spec. No source code changed; the session hook still builds `.venv` in a cloud session, and `bash -n` passes on it. `git grep -i "openspec\|opsx"` outside `.specworks/` finds nothing.
