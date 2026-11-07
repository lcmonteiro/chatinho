# Proposal

## Why

A peer that works on code — an `AgentConnector` writing a fix, a reviewer reading it — has nowhere to
work: the chat carries text and attachments, and nothing in it is a directory. A peer needs an
isolated place of its own, a git worktree on a branch of its own, whose work the rest of the chat
(the user, and other peers) can see without being able to change it.

## What Changes

- A sixth role in `ChatSession`: `workspaces=`, a **provider** that is not a peer — no id, in nobody's
  roster, granted what it declares — like the router.
- Two new hooks, a pair like `HookLocate`/`HookLink`:
  - `HookWorkspace` grants `workspace(name=None)` to a peer. With no name it returns the peer's own
    `Workspace`; with another peer's name it returns that peer's `WorkspaceView`, read-only.
  - `HookProvision` demands `provision(owner, name)` on the provider, which the session calls to
    resolve every `workspace` grant.
- **One writer per workspace.** The owner reads and writes; every other peer, and the user, only
  read. A view has no writing operation at all — the restriction is structural, not a runtime check.
- **One workspace per peer**, keyed by the peer's *name* (ids change between sessions), created lazily
  on the first `workspace()` as a git worktree on branch `peer/<name>`, reused across restarts, and
  never removed by `close()`: it holds work, not cache.
- **Operations are declared methods.** `WorkspaceView` (`read`, `ls`, `grep`, `diff`, `log`) and
  `Workspace(WorkspaceView)` (`write`, `delete`, `commit`) mark each operation with `@operation`;
  a writing one says `writes=True` and runs under the workspace's lock. Extending is subclassing:
  the provider takes the `view` and `workspace` classes, and refuses a workspace class that is not a
  subclass of the view class, or a view class that declares a writing operation.
- `grep` searches the working tree with Python's `re`, over the files git tracks or would track,
  with an optional `multiline` mode in which a match spans lines, and a `limit`.
- `GitWorktrees(repo, base=None, view=WorkspaceView, workspace=Workspace)`: the provider shipped,
  standard library only, running git with `asyncio.create_subprocess_exec` and reading files in a
  thread.
- `WorkspaceCommand` (`/ws`): lists the workspaces, shows a workspace's diff as an attachment, and
  merges or drops one — merge and drop only when run by the user (`by == LOCAL`).
- `AgentConnector` gets one `ws_<operation>` tool per operation the connector can reach, derived from
  the declarations, when it declares `HookWorkspace`.

Out of scope: an operation that runs arbitrary commands (`run`) and exposing workspaces through
`McpFrontend`. Both fit the design and are left for their own changes.

## Capabilities

### New Capabilities

- `peer-workspaces`: the workspace role in the session, the `HookWorkspace`/`HookProvision` pair, the
  one-writer access model, one workspace per peer and its lifecycle, the `GitWorktrees` provider and
  the `/ws` command.
- `workspace-operations`: operations declared as methods with `@operation`, the default read and
  write operations (including multiline `grep`), how they are discovered, and how the set is
  extended by subclassing `WorkspaceView` and `Workspace`.

### Modified Capabilities

- `agent-connector`: a connector that declares `HookWorkspace` gets `ws_<operation>` tools for its own
  workspace and read-only tools for other peers' workspaces.

## Impact

- New package `src/chatinho/workspaces/` (operations, views, the git provider) — standard library
  only, so the core still installs nothing; git is needed at runtime, not at import.
- `hooks.py`: fifteen hooks become seventeen. `docs/SPEC.md`, its fitness test in
  `tests/test_architecture.py`, `examples/hooks.py` and CLAUDE.md all name the count and must follow.
- `session.py`: a `workspaces` parameter and the routing of `workspace` to `provision`.
- `builder.py`: `build_chat_session` and `build_mcp_session` accept `workspaces=`.
- `connectors/agent.py`: the `ws_` tools.
- `commands/`: `WorkspaceCommand`.
- Public API: `Workspace`, `WorkspaceView`, `operation`, `Match`, `GitWorktrees`, `WorkspaceCommand`,
  `HookWorkspace`, `HookProvision`.
- CLAUDE.md's "the backend is the only thing that touches the file system" stops being true, on
  purpose, and is reworded.
