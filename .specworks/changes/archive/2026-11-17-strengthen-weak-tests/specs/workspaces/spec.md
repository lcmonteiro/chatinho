# Spec Delta: workspaces

## MODIFIED Requirements

### Requirement: REQ-WS-001 The provider checks the classes it is given

`GitWorktrees(repo, view=..., workspace=...)` SHALL refuse, with `TypeError` when it is created, a view class that does not subclass `WorkspaceView`, a workspace class that does not subclass the view class, and a view class with a writing operation, naming the class or the operation. Given a valid pair, the owner gets the workspace class and everyone else the view class, so an operation added to the view reaches both.

#### Scenario: AC-WS-001.1 A workspace class that does not extend the view

- **WHEN** the provider is given a view class and a workspace class that does not subclass it
- **THEN** creating it raises `TypeError` saying the workspace must subclass the view

#### Scenario: AC-WS-001.2 A view with a writing operation

- **WHEN** the provider is given a view class that declares a writing operation `scribble`
- **THEN** creating it raises `TypeError` naming `scribble`

#### Scenario: AC-WS-001.3 An extended pair

- **WHEN** the provider is given a view with an added read operation and a workspace that subclasses it
- **THEN** the owner gets the workspace class, another peer the view class, and both can call the added operation

#### Scenario: AC-WS-001.4 A view class that is no WorkspaceView

- **WHEN** the provider is given a view class that does not subclass `WorkspaceView`
- **THEN** creating it raises `TypeError` saying the view must subclass `WorkspaceView`

### Requirement: REQ-WS-002 The provider starts on a repository and a base

At `initialize()` the provider SHALL check that `repo` is a directory, that it is a git repository and that its base exists, raising `ValueError` otherwise. The base is the branch checked out when it starts, or the commit checked out when `HEAD` is detached, unless one is given by name.

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

#### Scenario: AC-WS-002.5 Not a directory

- **WHEN** the provider starts on a path that is a file, or does not exist
- **THEN** it raises `ValueError` saying it is not a directory

#### Scenario: AC-WS-002.6 A detached HEAD

- **WHEN** the provider starts with no base given while `HEAD` is detached at a commit
- **THEN** its base is that commit's sha, and a workspace branches from it

