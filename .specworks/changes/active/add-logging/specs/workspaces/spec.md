# Spec Delta: workspaces

## ADDED Requirements

### Requirement: REQ-WS-006 The provider logs merges and drops

`GitWorktrees` SHALL log, on the `chatinho` loggers at INFO, each workspace it merges, with its name, its branch and the base it was merged into, and each it drops, with its name and branch. A merge or a drop that fails SHALL be logged at WARNING with the workspace's name and the reason, and still fail as it does today.

#### Scenario: AC-WS-006.1 A merge

- **GIVEN** a workspace `dev` with a commit
- **WHEN** it is merged
- **THEN** a record names `dev`, its branch and the base

#### Scenario: AC-WS-006.2 A drop

- **WHEN** the workspace `dev` is dropped
- **THEN** a record names `dev` and its branch

#### Scenario: AC-WS-006.3 A merge that fails

- **GIVEN** a workspace `dev` whose merge conflicts with the base
- **WHEN** it is merged
- **THEN** the merge fails as it does today, and a warning names `dev` and the reason
