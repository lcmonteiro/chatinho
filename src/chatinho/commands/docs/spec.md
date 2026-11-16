# commands

## Purpose

The commands the library ships: `/help`, `/test` and `/ws`, which run when someone runs them and answer whoever did. It has no living spec yet; this records the behaviour it already has.

## Requirements

### Requirement: REQ-CMD-001 /ws lists the workspaces

`WorkspaceCommand(provider)` is the command `ws`. Run with no arguments it SHALL list the provider's workspaces, each with its branch and how many commits it is ahead of the base, or say there are none yet.

#### Scenario: AC-CMD-001.1 Listing

- **WHEN** `/ws` is run before any workspace exists, and after one has two commits
- **THEN** it answers `No workspaces yet.`, then the workspace with its branch and `2 commits ahead of main`

### Requirement: REQ-CMD-002 /ws diff shows a workspace's work

`/ws diff <name>` SHALL answer with a link to the workspace's diff against the base, attached as `<name>.diff` with media type `text/x-diff`. Anyone who can run commands may run it, an agent included.

#### Scenario: AC-CMD-002.1 The diff is an attachment

- **WHEN** `/ws diff dev` is run
- **THEN** it answers `dev's work: [dev.diff](dev.diff)`

#### Scenario: AC-CMD-002.2 The attachment holds the diff

- **WHEN** the answer's attachment is read
- **THEN** it is `dev.diff`, of type `text/x-diff`, and holds the workspace's changes

### Requirement: REQ-CMD-003 Only the user merges or drops

`/ws merge <name>` SHALL merge the workspace into the base and `/ws drop <name>` SHALL remove it and its branch, each answering what it did. Both MUST raise `PermissionError` when run by anyone but the user, changing nothing. A merge that conflicts MUST raise `MergeConflict` naming the files, and leave the base as it was.

#### Scenario: AC-CMD-003.1 Merging

- **WHEN** the user runs `/ws merge dev`
- **THEN** it answers that dev's workspace was merged, the base has its commits, and dev is then 0 commits ahead

#### Scenario: AC-CMD-003.2 A peer cannot merge or drop

- **WHEN** a peer other than the user runs `/ws merge` and `/ws drop`
- **THEN** each raises `PermissionError`, the base is unchanged, and the peer can still run `/ws diff`

#### Scenario: AC-CMD-003.3 A conflicting merge

- **WHEN** a merge conflicts on `README.md`
- **THEN** it raises `MergeConflict` naming `README.md`, and the base is unchanged

#### Scenario: AC-CMD-003.4 Dropping

- **WHEN** the user runs `/ws drop dev`
- **THEN** it answers that dev's workspace was dropped, its branch is gone, and dev's next workspace starts from the base

### Requirement: REQ-CMD-004 /ws refuses what it cannot do

`/ws` with an unknown subcommand, or a subcommand without its name, MUST raise `ValueError`; with a name that is no workspace it MUST raise `KeyError`.

#### Scenario: AC-CMD-004.1 What it refuses

- **WHEN** `/ws frobnicate dev`, `/ws diff`, `/ws diff ghost` and `/ws merge ghost` are run
- **THEN** the first two raise `ValueError` and the last two `KeyError`

### Requirement: REQ-CMD-005 /ws is a command like any other

`/ws` SHALL be given to a session like any command; the builders MUST NOT add it when given a workspace provider. `/help` SHALL list it when it is given.

#### Scenario: AC-CMD-005.1 The builders add none

- **WHEN** a chat is built with `/help` and a workspace provider
- **THEN** its only command is `help`

#### Scenario: AC-CMD-005.2 Help lists it

- **WHEN** a session has `/help` and `/ws` and `/help` is run
- **THEN** its answer lists `/ws`
