# workspace-backend Specification

## Purpose
Lets a workspace, or a read-only view of one, be handed to a LangChain deep agent as its file backend, so the agent works in the peer's git worktree with the tools it already has, under the same one-writer rule as the rest of the chat.

## Requirements

### Requirement: A workspace is a deep agents backend
`WorkspaceBackend(workspace)` SHALL take a writable workspace or a read-only view and SHALL be an instance of deep agents' `BackendProtocol`, so that `create_deep_agent(backend=...)` and `CompositeBackend` accept it, alone or as one of a composite's routes. It MUST NOT be an instance of `SandboxBackendProtocol`.

#### Scenario: Passed to create_deep_agent
- **WHEN** a deep agent is created with `backend=WorkspaceBackend(ws)` and runs `write_file("/a.txt", "hi")`
- **THEN** `a.txt` holds `hi` in the workspace's worktree

#### Scenario: A route of a composite
- **WHEN** a deep agent's backend is a `CompositeBackend` whose default is the backend of `dev`'s workspace and whose route `/peers/reviewer/` is the backend of `reviewer`'s view, and it reads `/peers/reviewer/notes.md`
- **THEN** it gets `notes.md` from reviewer's workspace

#### Scenario: No shell
- **WHEN** a deep agent with a `WorkspaceBackend` calls its `execute` tool
- **THEN** it gets deep agents' own error for a backend without a shell, and nothing runs

### Requirement: Paths are absolute and rooted at the workspace
Every path the backend takes SHALL be absolute, with `/` being the root of the workspace, and every path it returns MUST be absolute in the same way. A path that leaves the workspace MUST be answered with an error result, and nothing read or written.

#### Scenario: A rooted path
- **WHEN** the backend is asked to read `/src/app.py`
- **THEN** it reads `src/app.py` in the workspace

#### Scenario: Escaping
- **WHEN** the backend is asked to read `/../../etc/passwd`
- **THEN** the result carries an error and no file outside the workspace is read

### Requirement: Calls answer with results, never exceptions
Every method of the backend SHALL return the result type the protocol defines for it (`LsResult`, `ReadResult`, `GlobResult`, `GrepResult`, `WriteResult`, `EditResult`, `DeleteResult`, and a response per file for uploads and downloads). A failure of the operation underneath, including a missing file, an ambiguous edit or a path outside the workspace, MUST become that result's `error`, never an exception.

#### Scenario: A missing file
- **WHEN** the backend is asked to read `/nope.txt` and it does not exist
- **THEN** it returns a `ReadResult` whose `error` names the file

#### Scenario: An ambiguous edit
- **WHEN** the backend is asked to edit `/a.txt` replacing text that occurs twice, without `replace_all`
- **THEN** it returns an `EditResult` whose `error` says the text is not unique, and the file is unchanged

### Requirement: Each protocol method maps onto one operation
The backend SHALL answer `ls`, `read` (with its `offset` and `limit`), `glob`, `grep`, `write`, `edit`, `delete`, `upload_files` and `download_files` through the workspace's operations of the same purpose, so the lock, the path rules and any behaviour a project's subclass gives those operations apply. `read` MUST report the line its window starts at. `grep` MUST search for the pattern as literal text, as the protocol defines, and MUST honour `max_count`, marking the result as truncated when more matches existed. `ls` and `glob` MUST describe each entry with its absolute path and whether it is a directory.

#### Scenario: Literal grep
- **WHEN** the backend greps for `a.b(` in a file holding `a.b(1)` and `axb(2)`
- **THEN** it returns only the line holding `a.b(1)`

#### Scenario: max_count
- **WHEN** the pattern matches 30 times and the backend greps with `max_count=10`
- **THEN** it returns 10 matches and the result is marked truncated

#### Scenario: A write goes through the lock
- **WHEN** the owning peer and its deep agent write the same file at the same time
- **THEN** the writes run one after the other

### Requirement: A view refuses writes with an error result
A backend made from a read-only view SHALL answer `write`, `edit`, `delete` and `upload_files` with an error result saying the workspace is read-only and naming its owner, and MUST change nothing. Its reading methods SHALL work as on a writable workspace.

#### Scenario: Writing to someone else's workspace
- **WHEN** a deep agent writes `/peers/dev/a.txt` through the backend of dev's view
- **THEN** it gets a `WriteResult` whose `error` says dev's workspace is read-only, and dev's worktree is unchanged

### Requirement: Async only
The backend SHALL implement the protocol's async methods (`als`, `aread`, `aglob`, `agrep`, `awrite`, `aedit`, `adelete`, `aupload_files`, `adownload_files`) and MUST run them without blocking the event loop. Its sync methods MUST raise `NotImplementedError` saying the backend is async only.

#### Scenario: Called synchronously
- **WHEN** code calls the backend's `read` instead of `aread`
- **THEN** it raises `NotImplementedError` saying the backend is async only

### Requirement: Packaged behind its own extra
`WorkspaceBackend` SHALL be importable from `chatinho` and from the module that defines it, and SHALL need the `deepagents` extra. Importing `chatinho`, or using workspaces without the adapter, MUST NOT import `deepagents`. Reading `WorkspaceBackend` off `chatinho` without the extra MUST raise `ImportError` naming `chatinho[deepagents]`.

#### Scenario: Without the extra
- **WHEN** `deepagents` is not installed and code reads `chatinho.WorkspaceBackend`
- **THEN** it raises `ImportError` naming `chatinho[deepagents]`

#### Scenario: Workspaces without deep agents
- **WHEN** code creates a `GitWorktrees` provider and uses a workspace
- **THEN** no `deepagents` module is imported
