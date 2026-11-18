# Refinement: add-observer-server

## Problem

Every chatinho chat keeps its record on its own: in a local `DatabaseBackend`,
or nowhere. Several chats running at once, on different machines, cannot be
followed from one place, and a chat reopened elsewhere starts with no memory.
Only final answers become messages: how an agent got there (its graph nodes,
its model and tool calls, the asks it made on the way) is invisible outside
`AgentPeer`. Multi-agent workflows have made that the part people most need
to see.

## Outcomes

- One web page lists every chat by name; picking one shows its messages,
  updating live as they are said.
- Clicking a message shows its trace graph: each step, its state and text,
  linked to the step it followed, branching where steps ran side by side.
- A chat reopened on any machine with its name and key gets its history back
  from the hive.
- A chat's key reads and writes that chat only; the page needs an admin key.
- When the hive is unreachable, the chat keeps talking; what it could not
  send is resent in order, and anything lost is announced in a warning.
- The hive's API is documented on pages it serves itself.

## Context

**Observed:**
- `framework` (`src/chatinho/docs/`): seventeen hooks; attachments already
  bypass the message: the session hands them to the backend's `keep`
  (`HookKeep`) and `locate` reaches `link`. A trace would follow the same
  path. `docs/SPEC.md` is checked against the hook constants by
  `tests/test_architecture.py`.
- `backends` (`src/chatinho/backends/docs/`): `DatabaseBackend` is the only
  backend: `listen`, `load(since=, limit=)`, `forget`, `keep`, `link`, all
  SQLAlchemy run off the loop.
- `agents` (`src/chatinho/support/kits/agent/docs/`): `AgentPeer` runs a
  LangGraph graph `extract -> agent -> verify -> load`; nothing of a run but
  its answer leaves it.
- Packaging: the core installs nothing; FastAPI's stack (Starlette, uvicorn,
  pydantic) is already in the lock through `chatinho[mcp]`, SQLAlchemy
  through `chatinho[sql]`. The four layers are enforced by
  `tests/test_architecture.py`; a new top-level folder must belong to one.
- Keys are always read late from a key source (`support/parts/keys`).

**Assumed:**
- One database (SQLite by default, any SQLAlchemy URL) serves a hive for a
  handful of chats; no horizontal scaling is needed now.
- LangGraph's callbacks/stream events give the node and the model and tool
  call boundaries `AgentPeer` needs to emit traces.
- A plain HTML page with a little JavaScript and server-sent events is enough
  for the viewer, with no build step.

## Constraints

- [hard] Django was considered and set aside: FastAPI + SQLAlchemy + SSE.
- [hard] The hive and `HiveBackend` sit behind an extra (`chatinho[hive]`);
  `import chatinho` and the core stay dependency-free.
- [hard] The layering holds: `HiveBackend` is a backend and imports no other
  specialization; the server imports the framework's message and trace types,
  never the session.
- [hard] Nothing blocks the chat: sending to the hive never holds up a say,
  and a hive that is down never stops the conversation.
- [hard] Every chat has a name and its own key, made by a command on the
  hive's machine and printed once; only hashes are stored. A chat key reads
  and writes its own chat only; the page uses an admin key.
- [hard] A trace is not a message: it never enters `context()`, a model's
  memory or the terminal log.
- [soft] Trace text is cut short, so whole prompts and tool outputs are not
  stored.
- [soft] Works from a phone browser.

## Options

### Option A: the hive as each chat's backend, traces through new hooks

A FastAPI app in `src/chatinho/hive/` (models, API, viewer page, the
`chatinho-hive` command for chats and admin keys). `HiveBackend(url, key)`
in `backends/` does what `DatabaseBackend` does, over HTTP, plus `record`.
Two hooks: `HookTrace` grants `trace(msg_id, state, text, prev=None) ->
TraceID`, the session numbering traces and refusing an unknown `prev`;
`HookRecord` demands `record(trace)`, routed to the backend as attachments go
to `keep`. A `ChatTrace` holds `id`, `msg_id`, `state` (`running`, `done`,
`error`), `prev`, `text`, `frm`, `timestamp`. `AgentPeer` emits its nodes and
its model and tool calls; any peer may emit its own.

- **Pros:** one place for every chat's memory and view; traces are part of
  the library, usable by any peer and any backend; mostly dependencies the
  lock already has.
- **Cons:** seventeen hooks become nineteen; a new extra and a server to run;
  queueing and resending to write.
- **Effort:** L
- **Touches:** new `hive`; `framework`, `backends`, `agents`.
- **Outcomes:** meets all.

### Option B: the same on Django

Django + Django REST framework, Channels and a channel layer (Redis) for live
updates; the admin site as a first viewer.

- **Pros:** a viewer and accounts for free.
- **Cons:** synchronous at heart, against "nothing blocks"; Redis to run; a
  second ORM beside SQLAlchemy; nothing of it in the lock today.
- **Effort:** L
- **Touches:** as A.
- **Outcomes:** meets all, with more to run.

### Option C: an observer only

A peer that listens and copies messages and traces to the server; each chat
keeps its own `DatabaseBackend` or none.

- **Pros:** the chat never depends on the server.
- **Cons:** two records of every chat; a reopened chat does not get its
  history from the hive.
- **Effort:** M
- **Touches:** new `hive`; `framework`, `backends`, `agents`.
- **Outcomes:** fails "a chat reopened on any machine gets its history back".

## Recommendation

Option A, agreed. The hive is each chat's backend, on FastAPI, SQLAlchemy and
server-sent events, with traces as their own record through `HookTrace` and
`HookRecord`, a viewer page it serves, a name and a key per chat made by
`chatinho-hive chat add <name>`, and in-memory queueing with in-order resend
when it is down.

## Open Questions

- Is a session (one run of a chat) shown as a segment of the chat's history,
  or is a chat one continuous log? (who can answer: the user)
- Does `HiveBackend` speak HTTP with `httpx` or the standard library on a
  thread? (who can answer: specify/design)
- How long may a trace's text be, and how long is the resend queue?
  (who can answer: specify)
- Does the terminal show traces too? Out of scope for now.
  (who can answer: the user, in a later change)

## Candidate Capabilities

- `hive`: new (top level, `src/chatinho/hive`) - the server where every chat
  is kept and seen: its API, storage, keys, live stream and viewer page.
- `framework`: modified - `HookTrace`, `HookRecord`, `ChatTrace` and the
  session routing traces to the backend.
- `backends`: modified - `HiveBackend`, a chat's backend over HTTP, with
  queueing and resend.
- `agents`: modified - `AgentPeer` traces its nodes and its model and tool
  calls.
