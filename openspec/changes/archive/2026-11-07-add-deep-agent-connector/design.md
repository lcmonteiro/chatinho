# Design

## Context

See proposal.md for why. What shapes the approach:

- `AgentConnector` (`connectors/agent.py`) wraps `create_agent` in a graph of its own
  (`extract -> agent -> verify -> load`). It derives `OPTIONS` from `create_agent`'s signature,
  rebuilds the inner agent when the chat's shape changes (who is in it, which commands exist), and
  handles `checkpointer` at the outer graph.
- `create_deep_agent` (deepagents 0.7.34) takes `model`, `tools`, `system_prompt`, `middleware`,
  `response_format`, `checkpointer`, `name` and the rest of what `create_agent` takes. It also
  takes `subagents`, `skills`, `memory`, `permissions`, `backend`, `interrupt_on`, `store` and
  `cache`. It returns a compiled graph, as `create_agent` does.
- `add-peer-workspaces` provides the `workspace` grant, `WorkspaceBackend`, read-only views, and
  the `ws_` tools on `AgentConnector`.

## Goals / Non-Goals

**Goals:**

- One implementation of "an agent as a chat peer". The deep connector differs only in the factory,
  its options and its backend.
- A deep agent works in its workspace and reads the others' through its own file tools.
- Every option `create_deep_agent` takes is reachable, except those the chat owns.

**Non-Goals:**

- A shell. The backend is not a sandbox, so `execute` stays deep agents' "no shell" error until a
  `run` operation exists.
- Subagents with workspaces of their own. They share the connector's backend, as deep agents
  intends.
- Human-in-the-loop interrupts (`interrupt_on`) answered from the chat. The option is passed through,
  but resuming an interrupted run from a chat message is its own design.

## Decisions

### A subclass of AgentConnector with a different factory, not a copy

`AgentConnector` gets two class-level points of variation: the factory it calls (`create_agent`)
and the set of options that factory takes (derived from its signature, as `OPTIONS` is now).
`DeepAgentConnector` overrides both, plus one hook method that produces the extra keyword
arguments for the factory (the backend). Everything else is inherited unchanged: the outer graph,
memory, the chat tools, the link check, and `listen`/`answer`.

Alternatives considered:
- **A copy of `AgentConnector`.** Two places to fix every chat-side bug, and they would drift.
- **`AgentConnector(factory=create_deep_agent)`.** A public parameter whose valid values are exactly
  two functions, each with its own option set and its own rules (the backend). A class per factory
  states that better, and a project can still subclass for a third.

The seam is not behaviour, so `agent-connector`'s spec does not change. A test pins that an
`AgentConnector` still refuses deep-agent-only options, such as `subagents`.

### Option names: the chat keeps `memory` and `backend`

| deep agents option | in the connector | why |
|---|---|---|
| `memory` | `agent_memory` | `memory` is already the connector's `Query` for `context()`, in a published spec. Renaming that would break existing peers. |
| `backend` | refused, `TypeError` | The workspace is the backend. Accepting one would let a peer silently step outside the one-writer rule. |
| `name` | the connector's name, as for `AgentConnector` | |
| `checkpointer` | the outer graph's, as for `AgentConnector` | |
| everything else | passed through unchanged | |

### The backend: a composite built from the workspace grant

When the graph is built, the connector calls `workspace()` for its own workspace and
`workspace(name)` for every other peer that has one. It then builds:

```
CompositeBackend(
    default = WorkspaceBackend(own),                        # "/"
    routes  = {"/peers/<name>/": WorkspaceBackend(view)},   # one per other peer with a workspace
)
```

Which other peers *have* a workspace is asked with `workspace(name, create=False)`, which this
change adds to the grant. Without it the only door was `workspace(name)`, which makes a worktree
for any peer in the chat, so routing every peer would have given every peer a branch it never
asked for. The alternative, routing every peer lazily, would have needed a backend that defers
opening its view, and the routes would no longer say whose work exists.

The set of peers with a workspace becomes part of the shape that decides when the graph is rebuilt.
A peer whose workspace appears later is routed from the next question on, just as a peer that
joins later gets its `ask_` tool.

`/peers/` was chosen over `/workspaces/` because a model reasons about whose work it is reading,
not about the mechanism. Nothing else lives at `/peers/`, since the connector's own workspace is a
git worktree that never contains a top-level `peers/` the agent did not create itself. If it does,
the route shadows it, and that is stated in the system prompt guidance below.

**No provider means deep agents' default backend.** When the session has no workspace provider, the
connector catches the grant's error once, logs it, and passes no `backend`. The agent then has deep
agents' in-memory state backend, scoped to one question's thread. The alternative, refusing to
start, would make `DeepAgentConnector` unusable for a chat that only wants planning and subagents.

### Tools: only what the backend does not cover

The `ws_` derivation from `add-peer-workspaces` takes a filter. `DeepAgentConnector` excludes the
operations deep agents' own file tools reach through the backend: `ls`, `read`, `glob`, `grep`,
`write`, `edit` and `delete`. What remains is `ws_diff`, `ws_log` and `ws_commit` for its own
workspace, `ws_diff_of` and `ws_log_of` for the others, and every operation a project adds. A model
offered both `read_file` and `ws_read` would have to guess which one to use. With the filter it
never has to.

### Files and links

The link check applies, as in `AgentConnector`, to files a tool returned as artifacts. Files the deep
agent writes into its workspace are not attachments: they are in the worktree, and `ws_diff` is
how they are shown. `ws_diff` returns an `Attachment`, so a diff the agent produced is attached
and must be linked like any other.

### Packaging

`DeepAgentConnector` is in `connectors/deep.py`, lazily exported from `chatinho.connectors` and
`chatinho`, behind `chatinho[deepagents]`. That extra is the one `add-peer-workspaces` created,
widened to bring `langchain-openai` as well, because the connector turns an `Endpoint` into a chat
model exactly as `AgentConnector` does.

## Risks / Trade-offs

- [`AgentConnector`'s internals become an inheritance contract] → The seam is three members. Tests of
  both connectors run the same chat-side scenarios, so a change that breaks one subclass fails the
  suite.
- [deep agents' API is 0.x and moves] → The extra pins a compatible range. The connector's tests use
  the real `create_deep_agent` with a scripted model, not a stub of it.
- [A system prompt that does not mention `/peers/`] → The connector prepends one short paragraph to
  the system prompt, saying where its own files are and where the other peers' are, read-only. The
  user's own `system_prompt` follows it unchanged.
- [`interrupt_on` pauses a run that nothing in the chat resumes] → It is passed through, and a run
  that ends interrupted becomes an `ERROR` reply saying so, rather than hanging the ask.
- [The heaviest extra in the package] → Stated in CLAUDE.md's packaging table. `setup.sh` on Termux
  does not sync it.

## Open Questions

- Whether the paragraph about `/peers/` should be configurable or only replaceable by subclassing.
  Either answer leaves the specs and tasks as they are.
