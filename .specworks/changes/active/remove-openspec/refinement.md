# Refinement: remove-openspec

## Problem

chatinho kept OpenSpec beside specworks while its capabilities were baselined. All ten now have a living spec (#55, #56), so OpenSpec describes the same library a second time, in specs nobody updates any more, with its own skills, commands, CI job and session hook.

## Outcomes

- No `openspec/` folder, no OpenSpec skills or `/opsx` commands, no `openspec` CI job, and no OpenSpec CLI installed by the session hook.
- `CLAUDE.md` and `README.md` describe the specworks workflow, and the tests that pointed at an OpenSpec spec point at the living spec of their capability.
- The library's behaviour, tests and checks are unchanged.

## Context

**Observed:**
- `openspec/` holds `config.yaml`, 20 specs and the archive of past changes (170 tracked files).
- `.claude/skills/openspec-*` (12) and `.claude/commands/opsx/` (10).
- `.github/workflows/tests.yml` has an `openspec` job; `.claude/hooks/session-start.sh` installs the OpenSpec CLI at the version that job pins; `.claude/settings.json` sets `OPENSPEC_TELEMETRY`.
- `README.md` ("Changes go through OpenSpec") and `CLAUDE.md` (layout and Workflow) describe the OpenSpec workflow.
- Five test docstrings say "See openspec/specs/<name>".

**Assumed:**
- Nothing outside this repository reads `openspec/`.

## Constraints

- [hard] No behaviour change: the change is marked `skip-specs`.
- [hard] The session hook keeps building `.venv` in a cloud session.

## Options

### Option A: Remove everything, archive included

Delete `openspec/` whole, the skills, the commands, the CI job and the hook's OpenSpec part; rewrite the docs for specworks. The history of past changes stays in git.

- **Pros:** one system of specs, nothing left that nobody updates.
- **Cons:** the old proposals and designs are only in git history.
- **Effort:** S
- **Touches:** none (tooling and docs)
- **Outcomes:** meets all three.

### Option B: Keep the archive in a docs folder

As A, but move `openspec/changes/archive/` to `docs/history/openspec/`.

- **Pros:** the old reasoning stays browsable.
- **Cons:** a folder in a format nothing reads or updates.
- **Effort:** S
- **Touches:** none
- **Outcomes:** meets all three.

## Recommendation

Option A, chosen by the user.

## Open Questions

None.

## Candidate Capabilities

None: no behaviour change.
