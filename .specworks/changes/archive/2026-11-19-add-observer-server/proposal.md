# Proposal: add-observer-server

## Why

Each chat keeps its record alone, so several chats cannot be followed from one
place, a chat reopened elsewhere has no memory, and how an agent reached its
answer never leaves the agent. The hive is one server every chat keeps its
conversation in, with a page that shows every chat live and the trace graph of
any message (refinement: Option A).

## What Changes

- **Traces in the framework.** A trace is a record of one step of processing a
  message: `id`, the message it belongs to, its state (`running`, `done`,
  `error`), the trace it follows, its text, who traced it and when. Two new
  hooks: `HookTrace` grants `trace(msg_id, state, text, prev=None)`, which
  returns the new trace's id; `HookRecord` demands `record(trace)`, which the
  session calls on the backend, as attachments go to `keep`. A trace is never a
  message: nobody hears it and `context()` never returns it. Seventeen hooks
  become nineteen, and `docs/SPEC.md` gains their sections.
- **The agents trace their runs.** `AgentPeer` traces each node of its graph and
  each model and tool call, start and end, linked so the steps form a graph.
- **`HiveBackend(url, key)`**, a backend that keeps the conversation, the
  attachments and the traces in a hive over HTTP. It needs no extra: it speaks
  HTTP with the standard library, off the loop. Nothing it sends holds up the
  chat: a hive that is down is written to in memory and resent in order when it
  is back, and what is lost is announced. With `cache=<path>` it keeps a local
  SQLite mirror (standard library) of the chat and of what waits to be sent:
  a chat keeps its history when the hive is down, and nothing queued is lost
  across a restart.
- **The hive** (`chatinho.hive`, behind `chatinho[hive]`: FastAPI, uvicorn,
  SQLAlchemy). A chat is a name and a key, made with `chatinho-hive chat add
  <name>`, which prints the key once; an admin key is made with `chatinho-hive
  admin add`; only hashes are stored. A chat key reads and writes its own chat;
  the admin key reads every chat. `chatinho-hive serve` runs the API, its own
  OpenAPI pages, a live stream of each chat (server-sent events) and the viewer
  page.

## Capabilities

### New Capabilities

- `hive` (top level, `src/chatinho/hive`): the server every chat is kept and
  seen in: chats and keys, the API a chat's backend speaks, the views and the
  live stream, the viewer page, and how it is installed and run.

### Modified Capabilities

- `framework`: adds traces (`HookTrace`, `HookRecord`, the trace record and how
  the session hands traces to the recorder).
- `backends`: adds `HiveBackend`: a chat's archive, attachments and traces in a
  hive, its queue and resend, its optional local cache, and what it does when
  the hive is down or refuses its key.
- `agents`: adds the traces `AgentPeer` makes of a run.

## Related requirements

- REQ-CORE-002 left: names and ids are unchanged; a trace records the id.
- REQ-CORE-004 left: the new hooks are declared like any other.
- REQ-CORE-005 left: `trace` is granted only to whoever declares `HookTrace`.
- REQ-CORE-006, REQ-CORE-008, REQ-CORE-009, REQ-CORE-012, REQ-CORE-013 left: a
  trace is not a message, so delivery and asking are unchanged.
- REQ-CORE-014, REQ-CORE-015 left: delivery and nesting are unchanged.
- REQ-CORE-016 left: the backend's lifecycle is the one every peer has.
- REQ-CORE-019, REQ-CORE-020, REQ-CORE-022 left: traces never enter the
  conversation or the store.
- REQ-CORE-023, REQ-CORE-024 left: attachments go to the keeper as before; the
  recorder follows the same pattern under its own requirement.
- REQ-CORE-028 left: the new framework names and `HiveBackend` need only the
  standard library, so no new name sits behind an extra in `chatinho`; the
  hive's own extra is `hive`'s requirement.
- REQ-CORE-029 left: the builders are unchanged; a hive is passed as `backend=`.
- REQ-BACK-001, REQ-BACK-005, REQ-BACK-007 left: they describe
  `DatabaseBackend`, which is unchanged.
- REQ-AGENT-005 to REQ-AGENT-010 left: the workspace adapter is unchanged.
- REQ-CONN-013, REQ-CONN-020, REQ-CONN-021, REQ-CONN-022 left: the agent
  connectors' answers and workspaces are unchanged; tracing is `AgentPeer`'s.
- REQ-CONN-001, REQ-CONN-006, REQ-CONN-008, REQ-CONN-009 left: other
  connectors trace nothing in this change.
- REQ-FRONT-003, REQ-FRONT-005, REQ-FRONT-011, REQ-FRONT-022, REQ-FRONT-024,
  REQ-FRONT-025, REQ-FRONT-029 left: the frontends do not show traces.
- REQ-ROUTE-004, REQ-ROUTE-005, REQ-ROUTE-008, REQ-ROUTE-010 left: routing is
  unchanged.
- REQ-WS-004 left: workspaces are unchanged.

## Impact

- Code: `hooks.py` and `message.py` (the trace record and two hooks),
  `session.py` (the `trace` grant and the hand-over to the recorder),
  `support/kits/agent/` (tracing a run), `backends/hive.py`, and the new
  `hive/` package; `__init__.py` exports the new names.
- Layers: `hive/` is a specialization: it imports the framework and the parts,
  never `backends/`. The format a backend and the hive exchange lives in a part
  both import.
- Dependencies: a new extra `hive` (`fastapi`, `uvicorn`, `sqlalchemy`) and a
  `chatinho-hive` script; `uv.lock` updated. The core still installs nothing.
- Docs: `docs/SPEC.md` (nineteen hooks), `docs/architecture.md`, `CLAUDE.md`.
- Data: a new database owned by the hive; `DatabaseBackend`'s schema is
  untouched.

## Out of Scope

- A chat is one continuous log: runs of a chat (sessions) are not shown as
  separate segments.
- The terminal does not show traces.
- Connectors other than `AgentPeer`'s do not trace.
- A trace graph does not link to the messages a step asked of other peers;
  those asks are messages in the chat like any other.
- Editing, deleting or creating chats from the page; there is no remote admin
  API. Rotating or revoking a key beyond `chatinho-hive chat remove`.
- Running several hive processes against one database, and any scaling beyond
  one process.
- Syncing a cache with changes made in the hive by others (`chat remove`, or
  another process writing the same chat): the cache follows what this chat
  loads and writes.
