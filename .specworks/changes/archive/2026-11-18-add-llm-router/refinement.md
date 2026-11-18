# Refinement: add-llm-router

## Problem

In a room with two or more answering peers, a say that names nobody goes to nobody. `SimpleRouter` can
only route a reply back to its author or a say to the room's lone answering peer, so with several
models or services in the chat the person has to `@`-address every message to get an answer. The
library already says "a router may be a model"; none exists, and a peer carries nothing but its name
for one to decide on.

## Outcomes

- In a room with several answering peers, an unaddressed say is answered by the peer whose description
  fits it, without an `@`.
- A say meant for everyone stays a broadcast: heard by all, answered by none (`to=None`, as today).
- A reply to a peer's answer, or a say in a room with one answering peer, gets no extra delay: only a
  real choice waits for the model.
- When the model fails, times out or names no peer in the room, the say is still posted, as a
  broadcast, and the failure is logged: the chat never stalls or loses a message.

## Context

**Observed:**
- `routers` (`src/chatinho/routers/`, docs in `routers/docs/`): `SimpleRouter` declares `HookRoute`,
  `HookPeers` and `HookContext`; it routes a reply to its author (REQ-ROUTE-005) and any other say to
  the lone answering peer (REQ-ROUTE-004), else `None`.
- `framework` (`session.py`): `_say_for` **awaits** `router.route(msg)` before `_kept` and `_post`, so
  the say appears only once the router has decided. `_routed` accepts only another peer that answers;
  anything else is ignored with a warning, and an exception is logged, the say going to nobody
  (REQ-ROUTE-003).
- `route` returns one id or `None`: there is no way to name several recipients.
- `hooks.py`: `@tool(name, description)` sets a description on a command; `@connector(name, id=None)`
  sets a name only. A peer has no description today.
- `support/parts/keys/endpoint.py`: `Endpoint` (base_url + model + key source, named TOML profiles),
  stdlib only; `connectors/openai.py` builds an `AsyncOpenAI` from one, and takes a lent `llm`
  credential from `msg.credentials`. `support/parts/memory.py` turns a `Query` into what a model
  remembers.
- The builders give `SimpleRouter` unless given `router=` (REQ-ROUTE-006).

**Assumed:**
- An OpenAI-compatible chat completion is fast enough (around a second) to be awaited before a say is
  posted when there is a real choice.
- A short answer format (one peer name, or a word meaning everyone) is reliable enough from small
  models; anything else is treated as a broadcast.

## Constraints

- [hard] `routers/` imports the framework and the parts only, never `connectors/`
  (`tests/test_architecture.py`); `openai` sits behind the `chatinho[openai]` extra and is imported on
  first use, so `import chatinho` still needs no battery.
- [hard] Nothing blocks the loop: the model call is awaited.
- [hard] A broken model never silences a say: a failure or timeout routes to nobody.
- [hard] A broadcast is `to=None`; the session's routing contract (one id or None, before anyone
  hears) does not change.
- [soft] `SimpleRouter` stays the builders' default; the LLM router is opt-in via `router=`.
- [soft] A description on `@connector` is optional, so every existing peer keeps working unchanged.

## Options

### Option A: Router-only descriptions, model always asked

An `LLMRouter(endpoint, descriptions={name: text})` that asks the model for every unaddressed say.

- **Pros:** touches `routers` only; one rule.
- **Cons:** every say waits on the model, even in a one-peer room or for a follow-up; descriptions
  live apart from the peers they describe and drift when a peer is renamed.
- **Effort:** S
- **Touches:** routers
- **Outcomes:** meets 1, 2, 4; fails 3 (every say is delayed).

### Option B: Peer descriptions, SimpleRouter's rules first, model on a real choice

`@connector(name, description=…)` gives a peer a description (an instance may override it, as with
`name`). The new router applies `SimpleRouter`'s two rules first; only a say that is no reply to an
answering peer, in a room with two or more answering peers, goes to an OpenAI-compatible model built
from an `Endpoint`, with the roster's names and descriptions and the last few messages (a
configurable `Query`, small by default). The model answers a peer name or "everyone"; an unknown
name, an error or a timeout is a broadcast.

- **Pros:** no delay where there is nothing to choose; the description travels with the peer, so any
  future router or presentation can read it; reuses `Endpoint` profiles.
- **Cons:** touches the framework (`@connector`); a second router to keep consistent with
  `SimpleRouter`'s rules.
- **Effort:** M
- **Touches:** framework, routers
- **Outcomes:** meets all four.

### Option C: Post first, route after

Post the say as a broadcast at once, then let the model decide and ask the chosen peer.

- **Pros:** no visible delay ever.
- **Cons:** breaks "the route is written before anyone hears the say": listeners hear an unaddressed
  say that is then answered, and the conversation's `to` would change after the fact; a framework
  change to the session's ordering.
- **Effort:** L
- **Touches:** framework, routers
- **Outcomes:** meets 1, 3, 4; weakens 2 (a broadcast and a routed say look the same when heard).

## Recommendation

Option B, agreed with the user: broadcast stays `to=None`; descriptions on `@connector`; the model is
asked only when `SimpleRouter`'s rules leave a real choice; an OpenAI-compatible client from an
`Endpoint` behind `chatinho[openai]`; the say plus the last few messages through a configurable
`Query`.

## Open Questions

- The default timeout and the default context size. (who can answer: the user, at specify)
- The prompt and the answer format: a bare peer name, a JSON object, or a tool call; and the word for
  "everyone". (who can answer: specify/design)
- Whether a lent `llm` credential on the say is used, as `OpenAIConnector` does. (who can answer: the
  user, at specify)
- The class name (`LLMRouter`, `ModelRouter`) and whether it reuses `SimpleRouter` by composition.
  (who can answer: design)

Out of scope, stated so it is not assumed: answering by several peers at once; posting before
routing; showing descriptions in `/help`, the `@` popup or the MCP `peers` tool; changing the
builders' default router.

## Candidate Capabilities

- `routers`: modified - adds the LLM router: `SimpleRouter`'s rules first, then a model choosing a
  peer or a broadcast, failing to a broadcast.
- `framework`: modified - `@connector(name, description=…)`: a peer may describe what it is for.
