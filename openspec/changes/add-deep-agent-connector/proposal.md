# Proposal

## Why

`add-peer-workspaces` gives a peer a git worktree and makes it a deep agents backend, but nothing in
the chat uses that yet. LangChain's deep agents (`create_deep_agent`) are what a coding peer wants
to be: file tools a model is trained on (`read_file`, `edit_file`, `grep`…), planning, subagents and
skills. Today a chat can only host one by wrapping it by hand, and that loses everything
`AgentConnector` already does for a peer: the chat as tools, memory from the conversation,
attachments, and answering the user's says.

## What Changes

- `DeepAgentConnector`: a peer built with `create_deep_agent`. It takes the same parameters as
  `AgentConnector` and the options `create_deep_agent` adds (`subagents`, `skills`, `permissions`,
  `interrupt_on`, `store`…), and behaves as `AgentConnector` does in the chat: the `ask_<peer>`,
  `run_<command>` and `ask_user` tools, memory from `context()`, attachments and the link check,
  the user's says answered with a say, failures as `ERROR` replies.
- **Its backend is its workspace.** It declares `HookWorkspace`, and its deep agent's backend is a
  `CompositeBackend`. `/` is the connector's own workspace, writable. `/peers/<name>/` is each other
  peer's workspace, read-only. So the agent's own file tools work in its worktree and read the
  others'. A `backend` option is refused: the workspace is the backend.
- In a session with no workspace provider it still works, on deep agents' default in-memory backend,
  and says so in the log.
- **No duplicate tools.** The workspace operations deep agents' file tools already cover (`ls`,
  `read`, `glob`, `grep`, `write`, `edit`, `delete`) are not added again as `ws_` tools. The others
  are: `ws_diff`, `ws_log`, `ws_commit`, `ws_diff_of`, `ws_log_of`, and any operation a project adds.
- **`memory` keeps its chatinho meaning** (a `Query` for `context()`). Deep agents' own `memory`
  option, a list of `AGENTS.md`-style sources, is passed as `agent_memory`.
- `AgentConnector` gains an internal seam for which agent factory it calls and which options that
  factory takes. Its behaviour does not change.

## Capabilities

### New Capabilities

- `deep-agent-connector`: a chat peer built on `create_deep_agent`, with its workspace as its
  backend. Covers how it is configured, what it shares with `AgentConnector`, its backend
  composition, the tools it does and does not get, and its packaging.

### Modified Capabilities

- `peer-workspaces`: the `workspace` grant takes `create=False`, which answers `KeyError` for a
  workspace that does not exist yet instead of making it, so a peer can ask who has one without
  giving everyone a worktree. `AgentConnector`'s requirements are unchanged; the factory seam is
  internal.

## Impact

- New module `src/chatinho/connectors/deep.py`, behind `chatinho[deepagents]`. The extra is the one
  `add-peer-workspaces` introduces, with what `langchain` brings added to it.
- `connectors/agent.py`: the factory seam, and the `ws_` tool derivation made filterable.
- `connectors/__init__.py`, `chatinho/__init__.py`: a lazy export, its `TYPE_CHECKING` import, and
  the lazy-name table that the architecture test checks.
- `examples/`: a demo of a deep agent working in its workspace while another peer reviews it,
  driven by `tests/test_examples.py` with a scripted model.
- Depends on `add-peer-workspaces` (the workspace role and `WorkspaceBackend`). It cannot be applied
  before that change.
