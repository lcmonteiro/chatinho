# Spec Delta: commands

## ADDED Requirements

### Requirement: REQ-CMD-006 /test checks the chat is wired up

`TestCommand()` is the command `test`. Run, it SHALL say `Running checks…`, then `Peers: ` followed by the names of the peers other than the user, sorted (or `none`), then `Context: <n> message(s) in reach`, each as its own message, and answer `Checks done, for peer <id>.` with the id of whoever ran it. It takes no input it can refuse: its arguments are ignored.

#### Scenario: AC-CMD-006.1 Run by the user

- **WHEN** the user runs `/test` in a chat with the peers `weather` and `agent`
- **THEN** it says `Running checks…`, `Peers: agent, weather` and how many messages are in reach, in that order, and answers `Checks done, for peer 0.`

#### Scenario: AC-CMD-006.2 Run by a peer, with arguments

- **WHEN** the peer `bot`, id 1, the only peer besides the user, runs `/test extra words`
- **THEN** it says `Peers: bot`, ignores the words, and answers `Checks done, for peer 1.`

#### Scenario: AC-CMD-006.3 No peers

- **WHEN** the user runs `/test` in a chat with no other peer
- **THEN** it says `Peers: none`

## MODIFIED Requirements

### Requirement: REQ-CMD-002 /ws diff shows a workspace's work

`/ws diff <name>` SHALL answer with a link to the workspace's diff against the base, attached as `<name>.diff` with media type `text/x-diff`; a workspace with no changes is answered `<name>'s workspace has no changes.` with nothing attached. Anyone who can run commands may run it, an agent included.

#### Scenario: AC-CMD-002.1 The diff is an attachment

- **WHEN** `/ws diff dev` is run
- **THEN** it answers `dev's work: [dev.diff](dev.diff)`

#### Scenario: AC-CMD-002.2 The attachment holds the diff

- **WHEN** the answer's attachment is read
- **THEN** it is `dev.diff`, of type `text/x-diff`, and holds the workspace's changes

#### Scenario: AC-CMD-002.3 No changes

- **WHEN** `/ws diff dev` is run while dev's workspace has no changes
- **THEN** it answers `dev's workspace has no changes.` with no attachment

### Requirement: REQ-CMD-003 Only the user merges or drops

`/ws merge <name>` SHALL merge the workspace into the base and `/ws drop <name>` SHALL remove it and its branch, each answering what it did. Both MUST raise `PermissionError` when run by anyone but the user, changing nothing. A merge that conflicts MUST raise `MergeConflict` naming the files, and leave the base as it was.

#### Scenario: AC-CMD-003.1 Merging

- **WHEN** the user runs `/ws merge dev`
- **THEN** it answers that dev's workspace was merged, the base has its commits, and dev is then 0 commits ahead

#### Scenario: AC-CMD-003.2 A peer cannot merge or drop

- **WHEN** a peer other than the user runs `/ws merge` and `/ws drop`
- **THEN** each raises `PermissionError`, the base is unchanged, dev's workspace is still listed with its commit, and the peer can still run `/ws diff`

#### Scenario: AC-CMD-003.3 A conflicting merge

- **WHEN** a merge conflicts on `README.md`
- **THEN** it raises `MergeConflict` naming `README.md`, and the base is unchanged

#### Scenario: AC-CMD-003.4 Dropping

- **WHEN** the user runs `/ws drop dev`
- **THEN** it answers that dev's workspace was dropped, its branch is gone, and dev's next workspace starts from the base

