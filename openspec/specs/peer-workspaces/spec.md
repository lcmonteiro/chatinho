# peer-workspaces Specification

## Purpose
Gives each peer an isolated git worktree of its own to work in, which only that peer writes and which the user and the other peers can read, merge or drop, served to the session by a workspace provider that is not a peer.

## Requirements

### Requirement: A workspace provider is a role, not a peer
`ChatSession` SHALL take a `workspaces` parameter, and `build_chat_session` and `build_mcp_session` SHALL pass one through. The provider SHALL be registered by what it declares (`HookProvision`, which demands `provision`). It MUST NOT get an id, MUST NOT appear in `peers()`, in `/help` or in any roster, and MUST NOT hear the conversation. A second object declaring `HookProvision` in the same session MUST be refused when it is added.

#### Scenario: The provider is in no roster
- **WHEN** a session is built with a workspace provider and one connector
- **THEN** `peers()` lists the user and the connector, and nothing for the provider

#### Scenario: Two providers
- **WHEN** a second object declaring `HookProvision` is added to a session that already has a provider
- **THEN** adding it raises an error naming the hook

### Requirement: A peer reaches workspaces through one grant
A peer or command that declares `HookWorkspace` SHALL be granted `workspace(name=None, *, create=True)`, a coroutine. Called with no name, it SHALL return the caller's own workspace, which can read and write. Called with another peer's name, it SHALL return that peer's workspace as a view that can only read. Calling it from a peer for its own name MUST return its own writable workspace. Calling it when the session has no provider MUST raise an error saying so. Naming no peer in the session and no workspace that exists MUST raise `KeyError` naming it. A command calling it with no name MUST raise an error, because a command owns no workspace. With `create=False`, a workspace that does not exist yet MUST raise `KeyError` naming it, and the call MUST create nothing, for the caller's own workspace as for anyone else's.

#### Scenario: Its own workspace
- **WHEN** peer `dev` calls `workspace()` and then `write("a.txt", "hi")`
- **THEN** `a.txt` holds `hi` in `dev`'s workspace

#### Scenario: Another peer's workspace is read-only
- **WHEN** peer `reviewer` calls `workspace("dev")`
- **THEN** it can `ls`, `read`, `glob`, `grep`, `diff` and `log` dev's workspace, and the object it got has no `write`, `edit`, `delete` or `commit`

#### Scenario: No provider
- **WHEN** a peer declaring `HookWorkspace` calls `workspace()` in a session given no `workspaces`
- **THEN** the call raises an error saying the session has no workspace provider

#### Scenario: An unknown name
- **WHEN** a peer calls `workspace("nobody")` and no peer or workspace is named `nobody`
- **THEN** the call raises `KeyError` naming `nobody`

#### Scenario: Asking without creating
- **WHEN** peer `lead` calls `workspace("dev", create=False)` and `dev`, a peer in the chat, has never had a workspace
- **THEN** the call raises `KeyError` naming `dev`, and no worktree or branch is created for it

#### Scenario: Asking for one that exists
- **WHEN** `dev` has a workspace and `lead` calls `workspace("dev", create=False)`
- **THEN** it gets dev's workspace as a read-only view

### Requirement: One workspace per peer, keyed by its name
Each peer SHALL have at most one workspace, identified by the peer's name and not by its id. It SHALL be created the first time it is asked for, as a git worktree on a branch named `peer/<name>` started from the provider's base branch. When a worktree and branch for that name already exist, from this session or an earlier one, they MUST be reused, with their files and commits as they were. `close()` MUST NOT remove a workspace. The worktrees MUST live under the repository and MUST NOT appear as untracked files of the repository, and the provider MUST NOT edit any tracked file to achieve that.

#### Scenario: Created on first use
- **WHEN** peer `dev` calls `workspace()` for the first time
- **THEN** a branch `peer/dev` exists, started from the base branch, with a worktree checked out on it

#### Scenario: Reused after a restart
- **WHEN** `dev` commits in its workspace, the session closes, and a new session's `dev` calls `workspace()`
- **THEN** it gets the same branch and worktree, with the commit in its `log`

#### Scenario: Close keeps the work
- **WHEN** the session closes while `dev` has uncommitted changes in its workspace
- **THEN** the worktree and its changes are still on disk

#### Scenario: The repository stays clean
- **WHEN** a workspace has been created
- **THEN** `git status` in the repository shows no untracked worktree directory, and no tracked file changed

### Requirement: The base branch
The provider SHALL take the repository and an optional `base` branch. Without one, the base MUST be the branch the repository has checked out when the provider starts, and it MUST stay the same for every workspace of that session. A repository path that is not a git repository, or a `base` that does not exist, MUST be refused when the provider starts, naming it.

#### Scenario: Default base
- **WHEN** the repository has `main` checked out and the provider is given no `base`
- **THEN** every workspace branch starts from `main`

#### Scenario: Not a repository
- **WHEN** the provider is given a directory that is not a git repository
- **THEN** starting it raises an error naming the directory

### Requirement: Writing is serialized per workspace
Operations that write to one workspace SHALL run one at a time, in the order they were called. Operations that only read MUST NOT wait for each other. Several workspaces MUST NOT wait for each other.

#### Scenario: Two writes at once
- **WHEN** `dev` is answering two questions at once and both write the same file
- **THEN** the writes run one after the other, and the file holds the text of the one called last

### Requirement: Workspaces never block the chat
Git commands and file and search work SHALL run without blocking the event loop. While one workspace operation is running, every other peer MUST still be delivered messages and answer.

#### Scenario: A slow search
- **WHEN** `reviewer` greps a large workspace and the user says something to another peer at the same time
- **THEN** the other peer hears the say before the search finishes

### Requirement: The /ws command
A command named `ws` SHALL be provided:
- `/ws` lists every workspace: its name, its branch, and how many commits it is ahead of the base;
- `/ws diff <name>` answers with that workspace's diff as an attachment;
- `/ws merge <name>` merges the workspace's branch into the base branch and leaves the workspace in place;
- `/ws drop <name>` removes the worktree and deletes its branch.

`merge` and `drop` MUST be refused, changing nothing, unless the command was run by the user (`by == LOCAL`). A merge that conflicts MUST be aborted, leave the base branch as it was, and fail naming the conflicting paths. An unknown name or subcommand MUST fail saying so.

#### Scenario: Listing
- **WHEN** `dev` has two commits on its branch and the user runs `/ws`
- **THEN** the answer lists `dev`, `peer/dev` and two commits ahead

#### Scenario: Merging
- **WHEN** the user runs `/ws merge dev`
- **THEN** the base branch contains dev's commits, and dev's workspace still exists

#### Scenario: A model cannot merge
- **WHEN** an agent runs `/ws merge dev` through its `run_ws` tool
- **THEN** the command fails saying only the user can merge, and the base branch is unchanged

#### Scenario: A conflicting merge
- **WHEN** dev's branch conflicts with the base and the user runs `/ws merge dev`
- **THEN** the command fails naming the conflicting paths, and the base branch is as it was before

#### Scenario: Dropping
- **WHEN** the user runs `/ws drop dev`
- **THEN** the worktree is gone, `peer/dev` no longer exists, and dev's next `workspace()` creates a fresh one from the base

### Requirement: Packaged in the core
The workspace role, its hooks, the views and the git provider SHALL be importable from `chatinho` without any extra, and importing them MUST import only the standard library. The `git` executable SHALL be needed only when a provider starts, never at import.

#### Scenario: Importing without git
- **WHEN** code imports `chatinho` on a system with no `git` executable
- **THEN** the import succeeds
