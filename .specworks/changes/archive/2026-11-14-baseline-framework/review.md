# Review: baseline-framework

Base: `origin/main`

## Findings

- [x] R1 **spec-gap** REQ-CORE-001 said a numbered peer gets "the lowest free id from one upwards", but the session never goes back: it hands out the next id it would give, skipping any already taken, so an id freed below that is not reused (`src/chatinho/session.py:219`)
  - **Decision**: spec updated (ADDED REQ-CORE-001): the description now says "the next id the session would hand out, counting from one and skipping any id already taken". No criterion changed: AC-CORE-001.1, .3 and .4 already describe it.

## Changed files without tags

- `docs/architecture.md`, `docs/diagrams/architecture-blocks.d2`, `docs/diagrams/architecture-blocks.svg`: the first architecture, written by the adoption before this change; documentation.
- `.claude/skills/specworks-*/SKILL.md`, `.specworks/config.yml`: installed and written by the adoption before this change; configuration.

## Summary

Every source and test file this change touched gained only `@req` and `@ac` comment lines: 29 requirements tagged in six source files, 159 criteria in eleven test files, no new test and no code change. One wording drift in REQ-CORE-001 was corrected in the spec. The behaviour of a failing `answer` under a waiting `ask` is recorded as it is and left to `fix-ask-failure-reply`.
