# deep-agent-connector Specification

## Purpose
Puts a LangChain deep agent into a chat as a peer: built from `create_deep_agent`'s parameters, behaving in the chat exactly as `AgentConnector` does, and working in its own workspace while reading the other peers' through its own file tools.

## Requirements

### Requirement: Built from create_deep_agent's parameters
`DeepAgentConnector` SHALL take its name in the chat, a `model` and `tools`, the chat options `AgentConnector` takes (`memory`, `peers`, `commands`, `ask_user`, `link_retries`), and any other keyword argument `create_deep_agent` accepts. It SHALL pass those to `create_deep_agent` unchanged, except that the chat's tools are added to `tools`, the agent's `name` defaults to the connector's name, and deep agents' `memory` option is given as `agent_memory` and passed as `memory`. A `backend` option MUST raise `TypeError` when the connector is created, saying the workspace is the backend. A keyword argument `create_deep_agent` does not accept MUST raise `TypeError` naming it. Creating the connector MUST NOT call the model.

#### Scenario: Deep agents' options reach the agent
- **WHEN** a `DeepAgentConnector` is created with `subagents=[researcher]` and asked a question
- **THEN** the deep agent is built with that subagent

#### Scenario: memory and agent_memory
- **WHEN** a `DeepAgentConnector` is created with `memory=Query().last(5)` and `agent_memory=["/AGENTS.md"]`
- **THEN** the run is given the last five messages of the chat, and the deep agent is built with `memory=["/AGENTS.md"]`

#### Scenario: A backend is refused
- **WHEN** a `DeepAgentConnector` is created with `backend=some_backend`
- **THEN** creating it raises `TypeError` saying the workspace is the connector's backend

#### Scenario: AgentConnector is unchanged
- **WHEN** an `AgentConnector` is created with `subagents=[researcher]`
- **THEN** creating it raises `TypeError` naming `subagents`

### Requirement: The same peer as AgentConnector in the chat
Everything `AgentConnector` promises about how it behaves in the chat SHALL hold for `DeepAgentConnector`: one run of the agent per question and per user say it responds to, failures as `ERROR` replies naming the connector, the `ask_<peer>`, `run_<command>` and `ask_user` tools, memory from `context()`, attachments from tool artifacts and the link check, the user's says responded to with a say, and an `Endpoint` accepted as the model with its key read late. A run that ends interrupted, waiting for a human decision nobody in the chat can give, MUST become an `ERROR` reply saying it was interrupted, never an ask that waits forever.

#### Scenario: Asking another peer
- **WHEN** the chat has a peer `coder`, and the deep agent calls `ask_coder` with "Write a test"
- **THEN** `coder` is asked "Write a test", and its `Reply` is the tool's result

#### Scenario: The user's say
- **WHEN** the user says "Fix the login bug" with `to` unset
- **THEN** the connector says its answer replying to the user's message

#### Scenario: An interrupted run
- **WHEN** the connector has `interrupt_on={"write_file": True}` and the agent tries to write a file
- **THEN** the question gets an `ERROR` reply saying the run was interrupted

### Requirement: Its workspace is its backend
`DeepAgentConnector` SHALL declare `HookWorkspace`. When its session has a workspace provider, the deep agent's backend SHALL be composed so that `/` is the connector's own workspace, readable and writable, and `/peers/<name>/` is the workspace of each other peer that has one, read-only. The deep agent's own file tools (`ls`, `read_file`, `write_file`, `edit_file`, `glob`, `grep`) MUST therefore work in the connector's worktree, and MUST read other peers' worktrees and fail to write them. A peer whose workspace appears after a question MUST be reachable under `/peers/` from the next question on.

#### Scenario: Working in its own workspace
- **WHEN** the deep agent calls `write_file` on `/src/fix.py`
- **THEN** `src/fix.py` is written in the connector's own worktree

#### Scenario: Reading another peer's work
- **WHEN** peer `reviewer` has written `notes.md` in its workspace, and the deep agent calls `read_file` on `/peers/reviewer/notes.md`
- **THEN** the tool returns the contents of reviewer's `notes.md`

#### Scenario: Writing another peer's work
- **WHEN** the deep agent calls `write_file` on `/peers/reviewer/notes.md`
- **THEN** the tool reports that reviewer's workspace is read-only, and reviewer's worktree is unchanged

#### Scenario: A workspace that appears later
- **WHEN** peer `lab` creates its workspace after the connector has answered once, and the connector is asked again
- **THEN** the second run can read `/peers/lab/`

### Requirement: Without a provider it still works
When the session has no workspace provider, `DeepAgentConnector` SHALL run with deep agents' default backend and SHALL log once that it has no workspace. It MUST NOT fail to start or to answer for that reason, and it MUST get no `ws_` tools.

#### Scenario: A chat without workspaces
- **WHEN** a `DeepAgentConnector` is in a session given no `workspaces` and is asked a question
- **THEN** it answers, its file tools work on deep agents' default backend, and it has no `ws_` tools

### Requirement: Only the workspace tools its backend does not cover
With a workspace provider, the deep agent SHALL have `ws_` tools, derived as `AgentConnector`'s are, only for the workspace operations its own file tools do not already reach through the backend. It MUST NOT have `ws_` tools for `ls`, `read`, `glob`, `grep`, `write`, `edit` or `delete`, for its own workspace or for others'. Every other operation, including one a project adds, SHALL become a tool, as `ws_<op>` for its own workspace and, when it only reads, `ws_<op>_of` for others'.

#### Scenario: The default tools
- **WHEN** a `DeepAgentConnector` with a workspace is asked a question
- **THEN** its `ws_` tools are `ws_diff`, `ws_log`, `ws_commit`, `ws_diff_of` and `ws_log_of`

#### Scenario: A project operation
- **WHEN** the provider's view class adds an operation `symbols`
- **THEN** the deep agent has `ws_symbols` and `ws_symbols_of`

### Requirement: It is told where things are
The deep agent's system prompt SHALL begin with a short paragraph saying that `/` is the connector's own workspace and that `/peers/<name>/` holds the other peers' workspaces, read-only. The `system_prompt` the connector was given MUST follow it unchanged. Without a workspace provider the paragraph MUST be left out.

#### Scenario: The user's prompt is kept
- **WHEN** a `DeepAgentConnector` with a workspace is created with `system_prompt="Be brief."`
- **THEN** the model's system prompt mentions `/peers/` and then contains "Be brief."

### Requirement: Packaged behind the deepagents extra
`DeepAgentConnector` SHALL be importable from `chatinho.connectors.deep`, `chatinho.connectors` and `chatinho`, and SHALL need the `deepagents` extra. Importing `chatinho` or `chatinho.connectors` MUST NOT import `deepagents`. Reading `DeepAgentConnector` off `chatinho` without the extra MUST raise `ImportError` naming `chatinho[deepagents]`.

#### Scenario: Without the extra
- **WHEN** `deepagents` is not installed and code reads `chatinho.DeepAgentConnector`
- **THEN** it raises `ImportError` naming `chatinho[deepagents]`

#### Scenario: The core stays light
- **WHEN** code imports `chatinho`
- **THEN** no `deepagents` module is imported
