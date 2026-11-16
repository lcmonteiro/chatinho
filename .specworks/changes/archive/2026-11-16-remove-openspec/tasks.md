# Tasks: remove-openspec

## 1. Remove OpenSpec

- [x] 1.1 [code] Delete `openspec/`, `.claude/skills/openspec-*` and `.claude/commands/opsx/`; verify `git ls-files openspec .claude/commands/opsx` lists nothing
- [x] 1.2 [code] Delete the `openspec` job from `.github/workflows/tests.yml`, the OpenSpec part of `.claude/hooks/session-start.sh` and `OPENSPEC_TELEMETRY` from `.claude/settings.json`; verify the hook still runs and `grep -ri openspec .github .claude` finds nothing

## 2. Describe specworks instead

- [x] 2.1 [code] Rewrite the OpenSpec parts of `CLAUDE.md` and `README.md` for the specworks workflow, and point the five test docstrings at their capability's living spec; verify `grep -ri "openspec\|opsx"` over tracked files finds only the specworks archive and `fix-ask-failure-reply`, and lint passes
