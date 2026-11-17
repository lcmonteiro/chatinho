# Proposal: add-llm-router

## Why

In a room with two or more answering peers, a say that names nobody goes to nobody: `SimpleRouter`
cannot choose, so the person `@`-addresses every message to be answered. A router that asks a model
which peer a say is for, or whether it is for everyone, lets the room answer the way a person would
expect, and a peer needs a description for the model to choose on.

## What Changes

- `@connector(name, description="")` gives a peer an optional one-line description of what it is for;
  an instance may override it by setting `self.description`, as with `name`. A description that is
  not a string is refused with `ValueError`. Every existing peer keeps working unchanged.
- A new router, `LLMRouter` (`src/chatinho/routers/llm.py`), opt-in through `router=`:
  - it applies `SimpleRouter`'s two rules first: a reply goes back to the answering peer it replies
    to, and a say in a room with one answering peer goes to that peer, with no model call;
  - when those rules find no peer and two or more peers answer (the speaker and the frontend not
    counted), it asks an
    OpenAI-compatible model, built from an `Endpoint`, which peer the say is for, giving it the
    answering peers' names and descriptions, the say, and the earlier messages its `memory` (`Query`)
    selects;
  - the model answers a peer's name, or that the say is for everyone; for everyone, a name that is no
    answering peer, an error or a timeout, the say goes to nobody (a broadcast) and the failure is
    logged;
  - a key lent on the say as `llm` is used instead of its endpoint's own key, as `OpenAIConnector`
    does;
  - it imports `openai` only when built, so `import chatinho` and `chatinho.routers` still need no
    extra, and reading `LLMRouter` without `chatinho[openai]` raises `ImportError` naming it.
- `SimpleRouter` and the builders' default are unchanged.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `routers`: adds REQ-ROUTE-007 to REQ-ROUTE-011 (the LLM router: its rules before the model, what
  the model is given and how its answer is read, how it fails, the key it uses and where it is
  imported from).
- `framework`: modifies REQ-CORE-002 (a peer may carry a description).

## Related requirements

- REQ-CORE-002 modified: `@connector` gains `description`.
- REQ-CORE-012 left: an answer stays addressed to nobody; the router routes says only.
- REQ-CORE-018 left: the router uses `Query` as it is.
- REQ-CORE-028 left: its rule (a lazy name raises `ImportError` naming its extra) already covers
  `LLMRouter`; REQ-ROUTE-011 states it for the new name.
- REQ-ROUTE-001 left: the session consults the router exactly as before.
- REQ-ROUTE-002 left: `LLMRouter` is a router like any other, in no roster.
- REQ-ROUTE-003 left: the session still checks what a router returns; `LLMRouter` handles its own
  model failures before that (REQ-ROUTE-009).
- REQ-ROUTE-004 left: `SimpleRouter` is unchanged; `LLMRouter` keeps the same rule (REQ-ROUTE-007).
- REQ-ROUTE-005 left: as REQ-ROUTE-004.
- REQ-ROUTE-006 left: the builders still give `SimpleRouter` when given no router.
- REQ-CONN-001, REQ-CONN-002, REQ-CONN-003, REQ-CONN-005, REQ-CONN-006 left: `OpenAIConnector` is
  unchanged; the router has its own client.
- REQ-CONN-004 left: unchanged; REQ-ROUTE-010 gives the router the same rule for a lent key.
- REQ-CONN-011, REQ-CONN-015, REQ-CONN-017, REQ-CONN-018 left: the agent connectors are untouched.
- REQ-KEYS-001, REQ-KEYS-002, REQ-KEYS-003, REQ-KEYS-006, REQ-KEYS-008, REQ-KEYS-009, REQ-KEYS-010,
  REQ-KEYS-011, REQ-KEYS-012 left: `Endpoint` and the key sources are used as they are.
- REQ-AGENT-005 left: unrelated (matched on "route").
- REQ-FRONT-005 left: the terminal still never waits on others; a routed say is awaited by the
  session as it already is.
- REQ-FRONT-020 left: unrelated (matched on "route").
- REQ-FRONT-027 left: the MCP `peers` tool does not show descriptions (out of scope).
- REQ-CORE-001, REQ-CORE-003, REQ-CORE-026, REQ-CORE-029 left: ids, the frontend, the workspace
  provider and the builders are untouched.

## Impact

- `src/chatinho/hooks.py`: `connector()` takes `description`.
- `src/chatinho/routers/llm.py` (new), `routers/__init__.py` (a lazy `LLMRouter`),
  `src/chatinho/__init__.py` (`LLMRouter` in the lazy table and `__all__`, behind `chatinho[openai]`).
- Reuses `support/parts/keys` (`Endpoint`, `KeyUnavailable`) and `support/parts/memory.py` (what the
  model is given from the conversation).
- No new dependency: `openai` is already the `chatinho[openai]` extra. No data or schema change.
- Docs: `docs/SPEC.md` unchanged (no new hook); CLAUDE.md's public API count and battery table, at
  close.

## Out of Scope

- Several peers answering one say: a broadcast stays `to=None`, heard by all and answered by none.
- Posting a say before it is routed.
- Showing descriptions in `/help`, the `@` popup or the MCP `peers` tool.
- Changing the builders' default router.
- A LangChain or callable-based model client.

Assumptions (decided here, open to correction): the default `memory` is the last 6 messages without
failed replies; the default timeout is 10 seconds; the model is asked with temperature 0 and its
answer read as one line, a leading `@` and surrounding quotes or punctuation ignored, matched against
the answering peers' names case-insensitively, and the word `everyone` meaning a broadcast; a name two
answering peers share is a broadcast.
