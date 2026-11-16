# Design: routers

## Overview

`routers` decides who answers a say that names nobody. When a peer says
something with no `to`, the session hands the say to its router, the one it
was given as `router=`, and what `route` returns is written into the say's
`to` before anyone hears it. The router is a role, not a peer: no id, in no
roster, granted only what it declares. `SimpleRouter` (`simple.py`) is the
one the builders give: a reply goes back to the author of what it replies
to, and any other say to the room's lone answering peer.

![The router and where the session consults it (REQ-ROUTE-001, REQ-ROUTE-002, REQ-ROUTE-003, REQ-ROUTE-004, REQ-ROUTE-005, REQ-ROUTE-006)](diagrams/routers-blocks.svg)

## Decisions

- **`to` is the one field that says who answers, and the router fills it in**
  (REQ-ROUTE-001). It used to be two fields, `to` and `asked_of`, with the
  routing rule fixed inside the session; every reader had to know which to
  look at. Now the route is written into `to` before the say is heard.
  (baseline-routers)
- **The router is a role, not a peer** (REQ-ROUTE-002). It was a peer for a
  while (whoever declared `HookRoute`), which put a `router` in `/help`, in
  the MCP `peers` tool and in every roster, for a role nothing addresses. A
  connector that declares `HookRoute` is not consulted. (baseline-routers)
- **The default lives in the builders, not the session** (REQ-ROUTE-006). A
  `ChatSession` is the bare machinery and a rule nobody chose does not belong
  in it; a session built by hand routes nothing until given a router.
  (baseline-routers)
- **A broken router never silences a say** (REQ-ROUTE-003). A route that is
  not another answering peer is ignored with a warning, a router that raises
  is logged, and the say goes to nobody in both cases. (baseline-routers)
- **An answer is addressed to nobody, which tells a follow-up from an
  answer** (REQ-ROUTE-004, REQ-ROUTE-005). The answer a follow-up replies to
  was addressed to nobody, so `SimpleRouter` routes the follow-up back to its
  author. The cost: a listener that answers only `msg.to is None` stays quiet
  in a room with one answering peer. (baseline-routers)

## Interfaces

- `HookRoute`: demands `async route(msg) -> Optional[int]`, the id of the
  peer that answers *msg* (a say with `to` unset), or `None` for nobody.
- `ChatSession(router=...)`: the router must declare `HookRoute`, or
  `TypeError`; it gets the grants it declares, and its `initialize` and
  `shutdown` run with the chat's.
- Not consulted for an addressed say, what a command writes, an invocation
  (addressed to `TOOL`) or its answer, or a late answer to something put to
  its speaker.
- `SimpleRouter()`: declares `HookRoute`, `HookPeers` and `HookContext`; holds
  nothing, so one instance serves a session for its whole life. Neither rule
  counts the speaker or the frontend (`LOCAL`).
- `build_chat_session(router=None)`, `build_mcp_session(router=None)`: a
  `SimpleRouter` when none is given.

## Constraints

- A specialization: imports the framework only, never another
  specialization (`tests/test_architecture.py`).
- Standard library only; no extra is needed.
- `context()` is synchronous, so a reply's parent is found only in the window
  the session recalled; one older than that routes to nobody.
