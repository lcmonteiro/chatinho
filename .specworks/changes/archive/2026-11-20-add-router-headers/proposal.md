# Proposal: add-router-headers

## Why

`LLMRouter` cannot reach an OpenAI-compatible endpoint that requires extra
request headers, such as the GitHub Copilot API (`Editor-Version`): every
routing call there fails and becomes a broadcast. The specworks harness routes
its chat with `LLMRouter` on a Copilot login, so it needs the router to send
them.

## What Changes

- `LLMRouter` takes an optional `headers` mapping and sends it with every
  request to the model, with its endpoint's own key and with a key lent on the
  say as `llm`.
- `headers` that are not a mapping of strings to strings, or that hold
  `Authorization` in any letter case, are refused with `ValueError` when the
  router is built.
- Header values never appear in a log line or in the router's `repr`.
- A router built without `headers` behaves exactly as today.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `routers`: adds REQ-ROUTE-012, extra request headers on `LLMRouter`.

## Related requirements

- REQ-ROUTE-007 left: when the model is asked is unchanged.
- REQ-ROUTE-008 left: what the model is told and how its answer is read are unchanged.
- REQ-ROUTE-009 left: failures are still broadcasts; REQ-ROUTE-012 adds that header values stay out of the warnings it logs.
- REQ-ROUTE-010 left: a lent key still wins; refusing `Authorization` in REQ-ROUTE-012 is what keeps it so.
- REQ-ROUTE-011 left: `LLMRouter` stays behind `chatinho[openai]`.
- REQ-CORE-010 left: about `Reply`, unrelated.
- REQ-CORE-025 left: credentials on the message are unchanged; headers are per router, not per say.
- REQ-KEYS-001 left: key sources are unchanged; headers are not read from a key source.
- REQ-FRONT-013 left: "headers" there are the terminal's message headers.
- REQ-HIVE-003 left: the hive's `X-Hive-Key` header is unrelated.

## Impact

- Code: `src/chatinho/routers/llm.py` (`LLMRouter.__init__`, both client builds).
- Tests: `tests/routers/test_llm_router.py`; `tests/fakes/llm.py` records the headers a client was built with.
- No new dependency; the public API gains one keyword argument.
- Assumptions: the headers are copied when the router is built, so changing
  the caller's mapping later has no effect; an empty mapping is the same as
  none.

## Out of Scope

- Headers on `OpenAIConnector` or on `Endpoint` and its profiles.
- Headers per say, or lent like a key.
- Any client option besides headers (proxies, timeouts of the HTTP client).
