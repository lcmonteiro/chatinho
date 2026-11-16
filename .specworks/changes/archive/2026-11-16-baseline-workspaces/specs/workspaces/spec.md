# Spec Delta: workspaces

## Purpose

The workspace provider the library ships: `GitWorktrees`, which gives each peer its own git worktree on its own branch, and merges or drops one on request. It has no living spec yet; this records the behaviour it already has.

## ADDED Requirements

### Requirement: REQ-WS-001 The provider checks the classes it is given

`GitWorktrees(repo, view=..., workspace=...)` SHALL refuse, with `TypeError` when it is created, a workspace class that does not subclass the view class, and a view class with a writing operation, naming the class or the operation. Given a valid pair, the owner gets the workspace class and everyone else the view class, so an operation added to the view reaches both.

#### Scenario: AC-WS-001.1 A workspace class that does not extend the view

- **WHEN** the provider is given a view class and a workspace class that does not subclass it
- **THEN** creating it raises `TypeError` saying the workspace must subclass the view

#### Scenario: AC-WS-001.2 A view with a writing operation

- **WHEN** the provider is given a view class that declares a writing operation `scribble`
- **THEN** creating it raises `TypeError` naming `scribble`

#### Scenario: AC-WS-001.3 An extended pair

- **WHEN** the provider is given a view with an added read operation and a workspace that subclasses it
- **THEN** the owner gets the workspace class, another peer the view class, and both can call the added operation

### Requirement: REQ-WS-002 The provider starts on a repository and a base

At `initialize()` the provider SHALL check that `repo` is a git repository and that its base exists, raising `ValueError` otherwise. The base is the branch checked out when it starts, unless one is given by name.

#### Scenario: AC-WS-002.1 Not a repository

- **WHEN** the provider starts on a folder that is not a git repository
- **THEN** it raises `ValueError` saying so

#### Scenario: AC-WS-002.2 A base that does not exist

- **WHEN** the provider is given a base `nope` that does not exist
- **THEN** it raises `ValueError` saying `'nope' does not exist`

#### Scenario: AC-WS-002.3 The default base

- **WHEN** the provider starts with no base given while `main` is checked out
- **THEN** its base is `main`, and a workspace branches from it

#### Scenario: AC-WS-002.4 A base given by name

- **WHEN** the provider is given the base `release`
- **THEN** a workspace's base is `release`

### Requirement: REQ-WS-003 A workspace per peer, made on first use

`provision(owner, name, create=True)` SHALL make the workspace `name` on first use: a worktree at `<repo>/.chatinho/worktrees/<name>` on branch `peer/<name>`. The owner gets a workspace that writes; anyone else, a command included, gets a read-only view. Owner and readers share one tree, so one lock; two first asks at once make it once. With `create=False` nothing is made, and a workspace that does not exist is a `KeyError`. A name that cannot be a branch MUST raise `ValueError`.

#### Scenario: AC-WS-003.1 Created on first use

- **WHEN** the owner asks for its workspace for the first time
- **THEN** it gets a workspace at `.chatinho/worktrees/dev` on branch `peer/dev`

#### Scenario: AC-WS-003.2 Someone else's is a view

- **WHEN** another peer asks for that workspace
- **THEN** it gets a view with no `write`, `edit`, `delete` or `commit`

#### Scenario: AC-WS-003.3 A command gets a view

- **WHEN** a workspace is asked for with no owner
- **THEN** it is a view

#### Scenario: AC-WS-003.4 One tree per workspace

- **WHEN** the owner and another peer ask for the same workspace
- **THEN** both share one tree

#### Scenario: AC-WS-003.5 Two first asks at once

- **WHEN** two peers ask for a new workspace at the same time
- **THEN** both get the same tree

#### Scenario: AC-WS-003.6 Viewing without creating

- **WHEN** a workspace that does not exist is asked for with `create=False`
- **THEN** it raises `KeyError`

#### Scenario: AC-WS-003.7 A name that cannot be a branch

- **WHEN** a workspace is asked for with the name `../x`
- **THEN** it raises `ValueError` saying it cannot name a workspace

### Requirement: REQ-WS-004 Work outlives the chat, and the repository stays clean

A workspace SHALL be reused after a restart, also when only its branch survived, and closing the chat MUST keep its uncommitted work. The provider MUST leave the repository's own working tree and `git status` clean.

#### Scenario: AC-WS-004.1 Reused after a restart

- **WHEN** the owner commits, the provider is created again and the workspace asked for
- **THEN** its log holds the commit

#### Scenario: AC-WS-004.2 Only the branch survived

- **WHEN** the worktree folder is gone but its branch is not, and the workspace is asked for
- **THEN** its log holds the commit

#### Scenario: AC-WS-004.3 Close keeps the work

- **WHEN** the owner writes without committing and the chat is closed
- **THEN** the file is still in the worktree

#### Scenario: AC-WS-004.4 The repository stays clean

- **WHEN** workspaces are made and written to
- **THEN** `git status` of the repository is still empty

### Requirement: REQ-WS-005 Listing, merging and dropping

The provider SHALL list its workspaces' names and how many commits each is ahead of the base. `merge(name)` SHALL merge the workspace's branch into the base, wherever the base is checked out or in a temporary worktree it removes afterwards when it is checked out nowhere; a merge that conflicts MUST be aborted, raising `MergeConflict` with the conflicting paths, and leave the base and the repository as they were. `drop(name)` SHALL remove the worktree and its branch, so the next workspace of that name starts from the base. Merging or dropping a name that is no workspace MUST raise `KeyError`.

#### Scenario: AC-WS-005.1 Names and how far ahead

- **WHEN** `dev` has two commits and `lab` none
- **THEN** the names are `dev` and `lab`, 2 and 0 commits ahead

#### Scenario: AC-WS-005.2 Into the checked-out base

- **WHEN** `dev` is merged while `main` is checked out
- **THEN** `main` has its commit and its file

#### Scenario: AC-WS-005.3 Into a base checked out nowhere

- **WHEN** the base `release` is checked out nowhere and a workspace is merged
- **THEN** `release` has the commit, `main` does not, and the temporary worktree is gone

#### Scenario: AC-WS-005.4 A conflict is aborted

- **WHEN** the merge conflicts on `README.md`
- **THEN** it raises `MergeConflict` with that path, and the base and the repository are unchanged

#### Scenario: AC-WS-005.5 Dropping

- **WHEN** `dev` is dropped
- **THEN** it is no longer listed, its worktree and branch are gone, and a new `dev` starts from the base

#### Scenario: AC-WS-005.6 What does not exist

- **WHEN** a name that is no workspace is merged, or dropped
- **THEN** each raises `KeyError`
