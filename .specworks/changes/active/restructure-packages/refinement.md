# Refinement: restructure-packages

## Problem

chatinho is moving from OpenSpec to specworks, and specworks gives every
capability one code folder, where its living docs live too. Today's tree
is by role, but two behaviours are spread across role folders (the agents
over `connectors/agents/` and `helpers/agent/`; MCP over `frontends/`,
`connectors/` and `helpers/`), keys and endpoints are loose files in the
core, and `helpers/` mixes contracts two capabilities share with one
capability's own code. The capabilities cannot be registered so that a
file's folder says which capability it belongs to. It has to be settled
before the capabilities are registered and baselined, since every
baseline records paths.

## Outcomes

- Every capability's code is under its one folder, with no file of its own
  outside it; the folders that only group by role own no capability.
- The names `chatinho` exports (82) import and behave exactly as before:
  the 803 tests, ruff and mypy pass.
- `import chatinho` still needs no extra, the core stays stdlib-only and
  each battery needs only its own extra, still enforced by
  `tests/test_architecture.py`.
- A moved module's old path raises `ModuleNotFoundError`, and CLAUDE.md,
  `docs/SPEC.md`, the README and the examples name the new paths.

## Context

**Observed:**
- Role folders: `frontends/` (`chat/`, `mcp.py`), `connectors/`
  (`openai.py`, `mcp.py`, `agents/`), `backends/` (`database.py`),
  `routers/`, `commands/` (`help.py`, `test.py`, `workspace.py`),
  `workspaces/`, `helpers/` (`memory.py`, `mcp.py`, `agent/`).
- `connectors/agents/` holds only the two connector constructors; `AgentPeer`,
  the factories, graph, tools and results are in `helpers/agent/`.
- `keys.py` is imported by the builder, `McpFrontend`, `McpConnector`,
  `OpenAIConnector` and `AgentPeer`; `endpoint.py` by `OpenAIConnector` and
  `AgentPeer`. Shared infrastructure, not one connector's.
- `helpers/memory.py` (what a model remembers) is used by `OpenAIConnector`
  and `AgentPeer`; `helpers/mcp.py` (credentials key, attachment encoding)
  by `McpFrontend` and `McpConnector`. Both are stdlib-only.
- `frontends/__init__.py`, `connectors/agents/__init__.py` and
  `chatinho/__init__.py` resolve battery names lazily (PEP 562), by module
  path.
- Tests and examples import about 30 distinct submodules; the paths this
  change moves are named in `test_endpoint`, `test_openai_connector`,
  `test_agent_peer`, `test_basic_agent_connector`,
  `test_deep_agent_connector`, `test_architecture`, `tests/fakes/agent.py`,
  the README, `docs/SPEC.md` and CLAUDE.md.
- `openspec/specs/package-layout` promises `chatinho.session`,
  `chatinho.message`, `chatinho.hooks`, `chatinho.frontends.chat`,
  `chatinho.frontends.mcp` and `chatinho.builder`; none of them moves here.
- specworks has no capabilities registered yet (`specworks context`).

**Assumed:**
- Consumers import from `chatinho` itself: it is not on PyPI and is
  installed from a pinned commit.

## Constraints

- [hard] Only the names `chatinho` exports are promised; paths below it
  may move, with no compatibility alias (as `package-layout` already did
  for the `chat_*` modules).
- [hard] No behaviour change: modules move and are renamed, nothing else.
- [hard] The core stays stdlib-only and every battery behind its own
  extra; the architecture test keeps enforcing it.
- [soft] Keep an import path wherever a module can become a package of the
  same name.

## Options

### Option A: by role, a capability per leaf folder

Role folders stay and own nothing; each leaf folder under them is one
capability, and `shared/` becomes a role of its own: contracts two or more
capabilities agree on, stdlib-only, importing from no other role.

```
src/chatinho/                session: __init__, builder, session, hooks, message, query,
                             routers/, commands/ (help, test)
  keys/                      keys             ← keys.py (__init__), endpoint.py
  shared/mcp/                mcp-shared       ← helpers/mcp.py
  shared/memory/             memory-shared    ← helpers/memory.py
  frontends/chat/            chat-frontend
  frontends/mcp/             mcp-frontend     ← frontends/mcp.py
  connectors/openai/         openai-connector ← connectors/openai.py
  connectors/mcp/            mcp-connector    ← connectors/mcp.py
  connectors/agents/         agents-connector ← helpers/agent/* (factories in factories/)
  backends/database/         database-backend ← backends/database.py
  workspaces/                workspaces       + command.py ← commands/workspace.py
```

- **Pros:** keeps the role layout CLAUDE.md, `docs/SPEC.md` and the
  architecture test explain the library by; every `.py` that becomes a
  package keeps its path, so only `chatinho.endpoint`, `chatinho.helpers.*`
  and `chatinho.commands.workspace` move.
- **Cons:** 11 capabilities, some small; credential lending is split over
  `mcp-shared`, `mcp-frontend` and `mcp-connector`.
- **Effort:** M
- **Touches:** every capability below (none registered yet).
- **Outcomes:** meets all four.

### Option B: by capability, no role folders

One top-level package per capability (`keys/`, `terminal/`, `mcp/` with
server, connector and protocol, `openai/`, `agents/`, `database/`,
`workspaces/`), `shared/memory.py` the only shared module.

- **Pros:** 8 capabilities; MCP is whole in one folder; roles stay where
  the session reads them, in the declarations (`@frontend`, `@connector`,
  `@backend`).
- **Cons:** every `chatinho.frontends.*`, `chatinho.connectors.*` and
  `chatinho.backends.*` path breaks (about 40 imports in tests and examples);
  `package-layout`'s "each frontend lives under `chatinho.frontends`" is
  rewritten; the role folders the docs browse by are gone.
- **Effort:** L
- **Touches:** every capability.
- **Outcomes:** meets all four.

### Option C: minimal

Fold `helpers/agent/` into `connectors/agents/` and move `/ws` into
`workspaces/`; leave keys loose in the core and MCP as single files sharing
`helpers/mcp.py`.

- **Pros:** the smallest move.
- **Cons:** `openai`, both MCP ends and keys stay single files with no folder
  for their docs; `helpers/` keeps its mixed role.
- **Effort:** S
- **Touches:** agents, workspaces.
- **Outcomes:** fails outcome 1; meets 2-4.

## Recommendation

Option A, agreed with the user: it meets every outcome with the least
churn, keeps the role layout the documentation is built on, and gives
`shared/` a rule (only what two or more capabilities agree on) instead of
a catch-all `helpers/`. Names carry their role as a suffix; `keys` and
`workspaces` do not, being infrastructure and more than one role.

## Open Questions

- Should `chatinho.commands` keep exporting `WorkspaceCommand` once it lives
  in `workspaces/command.py`? The root export stays either way. (who can
  answer: the maintainer, at specify)

## Candidate Capabilities

None is registered yet; each is new in the top level, registered with
`specworks capability add` once this change lands (adopt stage 2), and
baselined from the OpenSpec specs listed.

- `session`: new ((top), `src/chatinho`) - peers, verbs and hooks, delivery,
  routing, context queries, replies, ids, attachments, lifecycle, built-in
  commands, builders, package layout. From message-delivery,
  message-routing, message-ids, answer-details, conversation-context,
  message-attachments, peer-lifecycle, package-layout.
- `keys`: new ((top), `src/chatinho/keys`) - key sources and endpoint
  profiles. From key-sources, endpoint-profiles.
- `mcp-shared`: new ((top), `src/chatinho/shared/mcp`) - the credentials key
  and attachment encoding both MCP ends agree on. From
  credential-delegation (the contract).
- `memory-shared`: new ((top), `src/chatinho/shared/memory`) - what a model
  remembers by default, and who said it. From openai-connector and
  agent-peer (memory).
- `chat-frontend`: new ((top), `src/chatinho/frontends/chat`) - the Textual
  terminal. No OpenSpec spec; CLAUDE.md.
- `mcp-frontend`: new ((top), `src/chatinho/frontends/mcp`) - a session
  served over MCP. From mcp-server, credential-delegation (server side).
- `openai-connector`: new ((top), `src/chatinho/connectors/openai`). From
  openai-connector.
- `mcp-connector`: new ((top), `src/chatinho/connectors/mcp`). From
  mcp-connector, credential-delegation (client side).
- `agents-connector`: new ((top), `src/chatinho/connectors/agents`) -
  `AgentPeer`, its factories, `BasicAgentConnector`, `DeepAgentConnector`.
  From agent-peer, agent-connector, deep-agent-connector.
- `database-backend`: new ((top), `src/chatinho/backends/database`) -
  `DatabaseBackend`. No OpenSpec spec of its own; part of
  message-attachments.
- `workspaces`: new ((top), `src/chatinho/workspaces`) - worktrees, their
  operations, `/ws`, the deep agents backend. From peer-workspaces,
  workspace-operations, workspace-backend.
