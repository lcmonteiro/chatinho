# Design

## Context

See proposal.md for why. What shapes the approach:

- The session already routes one grant to one demand through itself: `HookLocate` grants `locate`,
  and the session calls whoever declared `HookLink`. A workspace is the same shape.
- The router is the precedent for a role that is not a peer: no id, in nobody's roster, granted what
  it declares, and given by the builders rather than built into the session.
- The core is standard library only and enforced by `tests/test_architecture.py`.
- Nothing may block the loop: every peer, command and the terminal share one thread.
- A peer may be called concurrently, so two `answer`s may reach the same workspace at once.
- `AgentConnector` already derives tools from the chat (`ask_<peer>`, `run_<command>`).

## Goals / Non-Goals

**Goals:**

- A peer works in an isolated git worktree; everyone else can read what it did.
- Adding an operation means writing one method, and every consumer (agent tools, `/ws`) picks it up.
- The read-only view is enforced by structure, and type-checked for Python callers.

**Non-Goals:**

- Running arbitrary commands in a workspace. It needs its own design (sandbox, timeout, who may run).
- Several writers on one workspace, or several workspaces for one peer.
- Workspaces that are not git worktrees. The provider is a hook, so another kind can come later, but
  only the git one is designed here.
- Exposing workspaces over MCP.

## Decisions

### A role and a hook pair, not the backend, commands or a peer

`ChatSession(workspaces=provider)`. The provider declares `HookProvision` (demands
`provision(owner, name)`), and a peer that declares `HookWorkspace` is granted `workspace(name=None)`.

Alternatives considered:
- **In the backend.** The backend is what remembers. Putting git in it mixes memory with work, and
  every backend would then have to be a workspace provider too.
- **As commands** (`/ws read …`). Arguments are one string, which suits writing a file badly. Each
  peer's state would be hidden inside a command, and isolation would rest on `by`.
- **As a peer you `ask`.** Operations become natural language: unreliable for anything structural.
- **Composition** (`AgentConnector(workspace=GitWorktree(…))`, no hook). Simplest, and enough while
  only the peer sees its workspace. It fails the requirement that the user and other peers read it.

Like `backend=`, `workspaces=` is sugar for the role: the session registers the provider by what it
declares. The provider has no id and never hears the conversation.

### One writer: `Workspace` and `WorkspaceView` are two types

`workspace()` returns the caller's own `Workspace`. `workspace("dev")` returns dev's `WorkspaceView`.
`Workspace` subclasses `WorkspaceView`, so the owner can do everything a reader can. A view has no
`write` method at all, so mypy rejects the call, and so does Python at runtime.

The user reads through `/ws`. Merging into the base branch is not an operation, so no model can
reach it through its tools. It is only `/ws merge`, and the command refuses unless `by == LOCAL`.
That refusal is policy inside a command, not structure. It is stated here so it is not mistaken
for an oversight.

Alternative: one type plus a runtime access filter. This was rejected because it gives up the type
check for nothing that subclassing cannot also give.

### Operations are methods marked `@operation`; extending is subclassing

```python
class WorkspaceView:
    @operation("Search with a regex, optionally across lines")
    async def grep(self, pattern: str, path: str = ".", glob: Optional[str] = None,
                   multiline: bool = False, limit: int = 100) -> List[Match]: ...

class Workspace(WorkspaceView):
    @operation("Write a file", writes=True)
    async def write(self, path: str, text: str) -> None: ...
```

`operations_of(cls)` returns the marked methods in definition order, inherited ones included. Every
consumer derives from it: the agent's `ws_<op>` tools take their schema from the method's signature,
and `/ws` lists them. A writing operation runs under the workspace's `asyncio.Lock`, and the
`@operation` wrapper takes it, so no operation has to remember to.

To extend, subclass the layer the operation belongs to, and the owner's class inherits from both:

```
   WorkspaceView  <--  MyView (+ symbols)
        ^                 ^
   Workspace   <------  MyWorkspace (+ fix)
```

`GitWorktrees(repo, view=MyView, workspace=MyWorkspace)` validates at construction. The workspace
class must be a subclass of the view class, otherwise a read operation added only to the view would
be invisible to its owner. The view class must declare no writing operation. Both are refused where
the caller wrote them, for the same reason `ChatStyle` refuses a bad `local_align`.

Alternatives considered:
- **A fixed `Protocol`.** Every new operation would touch the protocol, each provider, the agent
  tools and `/ws`.
- **A registry of operation classes**
  (`operations=[Grep(), Write()]`, `ws.call("grep", …)`). Extensible, but every call is `Any` to
  mypy, and the one-writer rule becomes a filter.

The cost: CLAUDE.md says peers have no base class. Here the base class is the behaviour being
inherited, not a label, so the rule is not broken in spirit. That reasoning goes into CLAUDE.md.

### Underneath the operations: a small `Tree`

Operations do not call git or the file system directly. They call a `Tree`, which is created per
workspace and holds the worktree's root and the base branch. It offers `resolve(path)`,
`git(*args)`, `files(path, glob)` and reading and writing bytes. `resolve` is the only door to a
path. It resolves symlinks and refuses anything outside the root with `ValueError`, so an
operation written by a user cannot escape by forgetting to check. `git` uses
`asyncio.create_subprocess_exec`. File I/O and regex work go to `asyncio.to_thread`.

### One workspace per peer, keyed by name, lazily created, never removed by `close()`

| event | effect |
|---|---|
| first `workspace()` of a peer | `git worktree add <repo>/.chatinho/worktrees/<name> -b peer/<name> <base>` |
| restart | the worktree and the branch exist, so they are reused |
| `/ws merge <name>` | `git merge peer/<name>` on the base. The worktree stays |
| `/ws drop <name>` | `git worktree remove`, then the branch is deleted |
| `close()` | nothing |

The key is the name because ids are numbered per session and the work must outlive one. One
worktree per thread was considered and rejected: it solves a concurrency that is rare, and it costs
branches nobody can name. Two peers cover that case.

`base` defaults to the repo's current branch, read once when the provider starts, so every
worktree in a session branches from the same point. `.chatinho/` is added to the repo's
`.git/info/exclude` and not to `.gitignore`, so the provider never edits a tracked file.

### `grep`: Python's `re` over the files git lists

`git grep` is line-oriented and cannot match across a newline, even with `-P`. `rg -U` can, but it
is a binary that is not guaranteed to exist, Termux included. `grep` lists files with
`git ls-files --cached --others --exclude-standard`, which respects `.gitignore` and includes new
files not yet committed. It then runs `re` with `MULTILINE`, and adds `DOTALL` when
`multiline=True`, in a thread. Each `Match` has a path, a start line, an end line and the text,
truncated past a fixed length. Results stop at `limit`. A file that does not decode as UTF-8 is
skipped. A pattern that does not compile raises `ValueError` carrying `re`'s message, so a model
can correct it.

### What a view reads is the working tree

`read`, `ls` and `grep` read the files as they are now, uncommitted changes included. `diff` is the
working tree against the merge base with the base branch, so it shows what the owner did, not what
changed since their last commit. A reviewer sees the work in progress, which is the point of
reading it.

### Agent tools

A connector that declares `HookWorkspace` gets one `ws_<op>` tool per operation of its own
`Workspace`. It also gets one per operation of `WorkspaceView`, with a required `workspace`
argument naming the peer, which reads another peer's workspace. A `diff` result is returned as an
`Attachment`, which the connector already turns into an attachment of its answer.

## Risks / Trade-offs

- [A view reads uncommitted, half-written files] → Accepted: it is the work in progress. A
  reviewer that wants a stable point reads `log` and waits for a commit.
- [Writing operations serialize on one lock] → Per peer, by design. Two writers means two peers.
- [`grep` with `DOTALL` and a greedy `.*` can match most of a file] → Each match's text is
  truncated, and `limit` caps the count, so a model's tool result stays bounded.
- [A large repo makes `grep` slow] → It runs in a thread, so it is slow without freezing the chat.
- [A user-written operation that calls `open()` directly can escape the worktree] → `Tree.resolve`
  is documented as the only door. Python cannot enforce it, the same honest limit CLAUDE.md states
  for `_say`.
- [`/ws merge` conflicts] → The merge is aborted, the base branch is left as it was, and the
  command fails with the conflicting paths, which the terminal shows as an error toast.
- [The hook count changes from fifteen to seventeen] → `docs/SPEC.md`, its fitness test,
  `examples/hooks.py` and CLAUDE.md change in the same task. The fitness test fails until they do.

## Migration Plan

Additive. A session given no `workspaces` behaves as today. A peer that declares `HookWorkspace` in
such a session is still granted `workspace`, and calling it raises an error saying the session has
no workspace provider, rather than returning `None` the way `locate` does: a missing workspace is a
misconfigured chat, not a file that was not found. Nothing is migrated. Rollback is removing the
role.

## Open Questions

- Whether `/ws merge` should also offer a squash. This can be added to the command later without
  touching the specs of the role or the operations.
