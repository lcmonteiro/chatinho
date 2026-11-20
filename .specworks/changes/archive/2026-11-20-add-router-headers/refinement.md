# Refinement: add-router-headers

## Problem

`LLMRouter` builds its `AsyncOpenAI` client from a key and a base URL only, so
it cannot reach an OpenAI-compatible endpoint that requires extra request
headers, such as the GitHub Copilot API (`Editor-Version`). Every routing call
to such an endpoint fails and the say becomes a broadcast. The specworks
harness, which runs its peers on a Copilot login, needs to route with
`LLMRouter`, so it is blocked on this.

## Outcomes

- A router given extra headers sends them on every request to the model, with
  its endpoint's own key and with a key lent on the say as `llm`.
- A router given no headers sends exactly what it sends today.
- Malformed headers are refused when the router is built, not on the first say.
- Header values never appear in a log line or the router's `repr`.

## Context

**Observed:**
- `src/chatinho/routers/llm.py`: `LLMRouter.__init__(endpoint, *, memory,
  timeout, credential)`; `_choose` opens `AsyncOpenAI(api_key=lent.reveal(),
  base_url=...)` for a lent key; `_own_client` builds and caches
  `AsyncOpenAI(api_key=key, base_url=...)` per key digest. Neither passes
  headers.
- `routers` capability, living spec `src/chatinho/routers/docs/spec.md`:
  REQ-ROUTE-007 to 011 describe `LLMRouter`; REQ-ROUTE-009.6 refuses a bad
  `timeout` with `ValueError` at build time, the pattern to follow.
- `tests/routers/test_llm_router.py` drives the router with the stubbed
  `AsyncOpenAI` in `tests/fakes/llm.py`.
- `OpenAIConnector` (`connectors/openai.py`) builds its client the same way;
  out of scope here.

**Assumed:**
- `openai.AsyncOpenAI(default_headers=...)` sends them on every request; that
  is the SDK's documented behaviour.

## Constraints

- [hard] The core imports nothing new; `LLMRouter` stays behind
  `chatinho[openai]` (REQ-ROUTE-011).
- [hard] With no headers, REQ-ROUTE-007 to 010 hold unchanged.
- [soft] Header values are treated like keys: kept out of logs and `repr`.
- [soft] Bad input refused at build time, as `timeout` is.
- [soft] chatinho's conventions: `typing` generics, `%`-style logging,
  aligned blocks, Google docstrings.

## Options

### Option A: a `headers=` keyword

`LLMRouter(..., headers=None)` takes a mapping of `str` to `str`, copied at
build time and sent as `default_headers` on both clients it builds; anything
else raises `ValueError`.

- **Pros:** smallest API; nothing new for a caller to learn; one place to test.
- **Cons:** covers headers only, not proxies or other client options.
- **Effort:** S
- **Touches:** `routers`
- **Outcomes:** meets all.

### Option B: a client factory

`LLMRouter(..., client=None)`, a function building the `AsyncOpenAI` from a
key and base URL, so the caller adds headers or anything else.

- **Pros:** general; covers needs beyond headers.
- **Cons:** `openai`'s type enters the API; closing a caller-built client
  becomes unclear; part of the router's job moves to the caller.
- **Effort:** M
- **Touches:** `routers`
- **Outcomes:** meets all, at a larger API.

## Recommendation

Option A, agreed with the user: a `headers=` keyword on `LLMRouter`, for its
own and lent-key clients, validated at build time, with values kept out of
logs and `repr`. `OpenAIConnector` and `Endpoint` are left as they are.

## Open Questions

- Whether `Authorization` in `headers` is refused, or allowed to override the
  key. (who can answer: the user, at specify)

## Candidate Capabilities

- `routers`: modified - `LLMRouter` sends extra request headers.
