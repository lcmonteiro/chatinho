# agents

## Purpose

What the agent connectors are built from: a chat peer around any LangChain agent, which receives a factory that makes the agent, and an adapter that hands a workspace to a deep agent as its file backend. It has no living spec yet; this records the behaviour it already has.

## Requirements

### Requirement: REQ-AGENT-001 A peer around any agent factory

`AgentPeer(name, model, factory, ...)` SHALL be a chat peer around the agent its factory builds. A factory is any object with a `name`, an `options` set, a `covered` set and an `async build(model, tools, options, peer)` method. The peer MUST call `build` when its agent is first needed and again whenever the shape of the chat changes, never when it is created, giving it the chat's tools (an `ask_<peer>` tool for each other peer among them). Asked a question, the peer answers with the agent's last message.

#### Scenario: AC-AGENT-001.1 A custom factory

- **GIVEN** an `AgentPeer` with a factory of the caller's own, in a chat with a peer named `coder`
- **WHEN** it is asked a question
- **THEN** the factory's `build` was awaited once, with `ask_coder` among its tools, and the peer answers with the agent's last message

#### Scenario: AC-AGENT-001.2 Not built when created

- **WHEN** an `AgentPeer` is created and never asked anything
- **THEN** the factory's `build` is never called

#### Scenario: AC-AGENT-001.3 Rebuilt for a new peer

- **GIVEN** an `AgentPeer` that has answered once
- **WHEN** a peer named `lab` joins the chat and the `AgentPeer` is asked again
- **THEN** `build` was called a second time, with `ask_lab` among its tools and not among the first build's

### Requirement: REQ-AGENT-002 The factory says what it accepts

A keyword argument given to `AgentPeer` that is neither a chat option nor in the factory's `options` MUST raise `TypeError` when the peer is created, naming the factory and the argument.

#### Scenario: AC-AGENT-002.1 An option the factory does not take

- **GIVEN** a factory named `counting_factory` whose `options` lack `temperature`
- **WHEN** an `AgentPeer` is created with it and `temperature=0.2`
- **THEN** `TypeError` is raised saying `counting_factory` does not take `temperature`

### Requirement: REQ-AGENT-003 The factory says what its own tools cover

With `workspace=True` and a workspace provider, the agent SHALL get a `ws_<op>` tool for each workspace operation and a `ws_<op>_of` tool for each one that reads, except the operations named in the factory's `covered` set, which MUST get neither.

#### Scenario: AC-AGENT-003.1 Covered operations get no tools

- **GIVEN** an `AgentPeer` with `workspace=True`, a workspace provider, and a factory whose `covered` is `read`
- **WHEN** it is asked a question
- **THEN** the agent has neither `ws_read` nor `ws_read_of`, and has `ws_write` and `ws_diff_of`

### Requirement: REQ-AGENT-004 Where the kit is imported from

`AgentPeer`, `AgentFactory` and `BasicAgent` SHALL be importable from `chatinho.support.kits.agent` without importing `deepagents`; `DeepAgent` is importable from there only with it. None of them is exported from `chatinho`.

#### Scenario: AC-AGENT-004.1 Not in the top-level API

- **WHEN** `chatinho.AgentPeer` is read
- **THEN** `AttributeError` is raised

#### Scenario: AC-AGENT-004.2 The basic pieces need no deep agents

- **GIVEN** a process where `deepagents` cannot be imported
- **WHEN** `AgentPeer`, `AgentFactory`, `BasicAgent` and the basic agent connector are imported, and then `DeepAgent`
- **THEN** the first imports succeed, importing `DeepAgent` raises `ImportError`, and no `deepagents` module was loaded

### Requirement: REQ-AGENT-005 A workspace is a deep agents backend

`WorkspaceBackend(workspace)` SHALL take a writable workspace or a read-only view and be an instance of deep agents' `BackendProtocol`, accepted by `create_deep_agent(backend=...)` alone or as a route of a `CompositeBackend`. It MUST NOT be a sandbox backend: a deep agent's `execute` tool gets deep agents' own error for a backend without a shell.

#### Scenario: AC-AGENT-005.1 A backend, not a sandbox

- **WHEN** a `WorkspaceBackend` is made from a workspace
- **THEN** it is an instance of `BackendProtocol` and not of `SandboxBackendProtocol`

#### Scenario: AC-AGENT-005.2 A deep agent works in the workspace

- **WHEN** a deep agent created with `backend=WorkspaceBackend(ws)` writes `/fix.py` and reads it back
- **THEN** `fix.py` holds that text in the workspace's worktree, and the agent read it

#### Scenario: AC-AGENT-005.3 A route of a composite

- **GIVEN** a `CompositeBackend` whose default is dev's backend and whose route `/peers/reviewer/` is the backend of reviewer's view
- **WHEN** a deep agent reads `/peers/reviewer/notes.md`, writes to it, and calls `execute`
- **THEN** it reads reviewer's file, the write is refused as read-only and changes nothing, and `execute` answers that it cannot run

### Requirement: REQ-AGENT-006 Paths are absolute and rooted at the workspace

Every path the backend takes SHALL be absolute, `/` being the root of the workspace, and every path it returns MUST be absolute in the same way, a directory ending with `/` and marked as one. A path that leaves the workspace MUST be answered with an error result, and nothing read or written.

#### Scenario: AC-AGENT-006.1 A rooted path

- **WHEN** the backend writes and reads `/src/app.py`
- **THEN** the file is `src/app.py` in the workspace, and the read returns its content

#### Scenario: AC-AGENT-006.2 Escaping

- **WHEN** the backend is asked to read `/../../etc/passwd`
- **THEN** the result carries an error saying the path is outside, and no file data

#### Scenario: AC-AGENT-006.3 Paths come back absolute

- **WHEN** the backend lists `/` and `/src`, and globs `*.py`
- **THEN** each entry has its absolute path, `/src/` is marked a directory, and the glob returns `/src/app.py`

### Requirement: REQ-AGENT-007 Calls answer with results, never exceptions

Every async method of the backend SHALL return the result type the protocol defines for it. A failure of the operation underneath (a missing file, an ambiguous edit, a path outside the workspace) MUST become that result's `error`, never an exception.

#### Scenario: AC-AGENT-007.1 A missing file

- **WHEN** the backend is asked to read `/nope.txt`, which does not exist
- **THEN** it returns a result whose `error` names the file

#### Scenario: AC-AGENT-007.2 An ambiguous edit

- **GIVEN** a file holding `x` twice
- **WHEN** the backend edits `x` to `y` without `replace_all`, and then with it
- **THEN** the first result's `error` says the text is not unique and the file is unchanged, and the second reports 2 occurrences and no error

#### Scenario: AC-AGENT-007.3 A glob that leaves

- **WHEN** the backend globs `../*`
- **THEN** the result carries an error

### Requirement: REQ-AGENT-008 Each protocol method maps onto one operation

The backend SHALL answer `als`, `aread`, `aglob`, `agrep`, `awrite`, `aedit`, `adelete`, `aupload_files` and `adownload_files` through the workspace's operations of the same purpose, so the workspace's lock and path rules apply. `aread` MUST report the lines its window starts and ends at and the offset of what remains. `agrep` MUST search for the pattern as literal text and honour `max_count`, marking the result truncated when more matched. Uploads and downloads answer one response per file.

#### Scenario: AC-AGENT-008.1 Read reports its window

- **GIVEN** a file of 10 lines
- **WHEN** the backend reads it with `offset=4` and `limit=3`, then `offset=8` and `limit=5`, then `offset=50`, then `limit=0`
- **THEN** the first reports lines 5 to 7 and next offset 7, the second lines 9 to 10 and no next offset, the third an error, and the fourth that no lines were requested

#### Scenario: AC-AGENT-008.2 Literal grep

- **GIVEN** a file holding `a.b(1)` and `axb(2)`
- **WHEN** the backend greps for `a.b(`
- **THEN** it returns only the line holding `a.b(1)`

#### Scenario: AC-AGENT-008.3 max_count

- **GIVEN** a pattern that matches 30 times
- **WHEN** the backend greps with `max_count=10`, and without it
- **THEN** the first returns 10 matches marked truncated, and the second all 30

#### Scenario: AC-AGENT-008.4 A write goes through the lock

- **WHEN** the owning peer and the backend write the same file at the same time
- **THEN** the writes run one after the other

#### Scenario: AC-AGENT-008.5 Uploads and downloads

- **WHEN** the backend uploads a file and a path that leaves the workspace, then downloads the file and a missing one
- **THEN** each gets its own response: the file's with no error and its bytes back, the others with `invalid_path` and `file_not_found`

### Requirement: REQ-AGENT-009 A view refuses writes with an error result

A backend made from a read-only view SHALL answer `awrite`, `aedit` and `adelete` with an error result naming the owner's workspace, and `aupload_files` with `permission_denied`, and MUST change nothing. Its reading methods work as on a writable workspace.

#### Scenario: AC-AGENT-009.1 Writing to someone else's workspace

- **GIVEN** the backend of a view of reviewer's workspace
- **WHEN** it is asked to write, edit, delete and upload
- **THEN** each answers with an error, the first three naming reviewer's workspace, the file is unchanged, and reading it still works

### Requirement: REQ-AGENT-010 The backend is async only

The backend's sync methods MUST raise `NotImplementedError` saying the backend is async only.

#### Scenario: AC-AGENT-010.1 Called synchronously

- **WHEN** the backend's `read` is called instead of `aread`
- **THEN** it raises `NotImplementedError` saying it is async only

### Requirement: REQ-AGENT-011 Workspaces do not need the adapter

Using workspaces in a session without the adapter MUST NOT import `deepagents`.

#### Scenario: AC-AGENT-011.1 Workspaces without deep agents

- **WHEN** a session with a `GitWorktrees` provider starts and a workspace is written to
- **THEN** no `deepagents` module was loaded

### Requirement: REQ-AGENT-012 An agent traces its run

`AgentPeer` SHALL declare `HookTrace` and trace each step of a run on the message it answers or responds to: each node of its graph (`extract`, `agent`, `verify`, `load`), each model call and each tool call. A step SHALL be traced when it starts, with state `running`, and when it ends, with state `done` or `error`; the end follows the start. A step's start follows the step it ran in when it is the first inside it, and otherwise the last step that ended inside the same one; steps started from the same point (tool calls of one model call) follow the same trace. The text names the step: the node's name, `model <name>`, or `tool <name>` with its input, and on its end the output or the error's type, cut short.

#### Scenario: AC-AGENT-012.1 The nodes of a run

- **GIVEN** an agent peer with a scripted model that answers without tools, in a session with a recorder
- **WHEN** the peer is asked a question
- **THEN** the recorder holds a `running` and a `done` trace for each of `extract`, `agent`, `verify` and `load`, all for the question's id, each `done` following its `running`

#### Scenario: AC-AGENT-012.2 A tool call

- **GIVEN** a scripted model that calls one tool and then answers
- **WHEN** the peer is asked
- **THEN** there is a `tool <name>` start trace whose text holds the tool's input, following the end of the model call that asked for it, and an end trace holding its output

#### Scenario: AC-AGENT-012.3 Two tool calls at once

- **GIVEN** a scripted model that calls two tools in one turn
- **WHEN** the peer is asked
- **THEN** both tools' start traces follow the same trace

#### Scenario: AC-AGENT-012.4 A step that fails

- **GIVEN** a tool that raises
- **WHEN** the model calls it
- **THEN** that tool's end trace has state `error` and its text names the error's type

#### Scenario: AC-AGENT-012.5 Tracing never fails the run

- **GIVEN** a recorder whose `record` raises
- **WHEN** the peer is asked
- **THEN** it answers as it does with no recorder

#### Scenario: AC-AGENT-012.6 Each run is its own graph

- **WHEN** the peer is asked two questions at once
- **THEN** each question's traces follow only traces of the same question
