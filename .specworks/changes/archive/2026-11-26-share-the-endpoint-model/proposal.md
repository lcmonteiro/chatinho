# Proposal: share-the-endpoint-model

## Why

Three parts of chatinho call a model, and each builds its own client from an
`Endpoint`: `OpenAIConnector` and `LLMRouter` hold an `AsyncOpenAI` per key with
their own rotation rules, and the agents turn an `Endpoint` into an
`EndpointChatModel` of their own. The key that pays for a call can always come
with a message (`msg.credentials`), so the person asked for one model
abstraction in `support/` that takes the key per call, used by every component
that needs a model.

## What Changes

- New kit `support/kits/model/` (capability `models`), behind `chatinho[openai]`:
  `EndpointModel(endpoint, headers=None)`, the one model every component calls.
  - `await complete(messages, api_key=None, **params)`: one chat completion, with
    the key given for that call (a client built for it and closed after), or the
    endpoint's own key, read when the call needs it.
  - Its own key's client is kept, shared by concurrent calls, rebuilt when the key
    changes (the old one closed once idle), and closed by `close()`.
  - `chat_model()`: the same model as a LangChain chat model taking `api_key` per
    call or from the run's `configurable["api_key"]` (what `EndpointChatModel` did),
    imported only then, behind `chatinho[langchain]`.
  - `lent_key(msg, credential)`: the key a message lends under a name.
- `OpenAIConnector`, `LLMRouter` and `AgentPeer` all call their model through
  `EndpointModel`; none builds an OpenAI client or a LangChain OpenAI model itself.
- `EndpointChatModel` moves from `support/kits/agent/model.py` to the model kit.

## Capabilities

### New Capabilities

- `models` (top module), code path `src/chatinho/support/kits/model`: adds
  REQ-MODEL-001 to REQ-MODEL-006.

### Modified Capabilities

- `connectors`: REMOVES REQ-CONN-027, moved to REQ-MODEL-003 unchanged.

## Related requirements

- REQ-CONN-004 left: `OpenAIConnector`'s lent key still wins; it now passes it to the model.
- REQ-CONN-005 left: what it asks and answers is unchanged.
- REQ-CONN-006 left: one client per key and the rotation rule hold, now kept by the model (REQ-MODEL-002).
- REQ-CONN-018 left: an `Endpoint` still becomes a chat model reading its key when called.
- REQ-CONN-026 left: the agent still answers with the lent key, through the model's `configurable["api_key"]`.
- REQ-CONN-027 removed: moved to REQ-MODEL-003.
- REQ-ROUTE-010 left: the router's lent key still wins.
- REQ-ROUTE-012 left: the router still validates its headers; the model sends them.
- REQ-KEYS-001 left: key sources unchanged.
- REQ-HIVE-003, REQ-FRONT-013, REQ-FRONT-024 to REQ-FRONT-028 left: unrelated (matched on "headers", "client" or "key").

## Impact

- Code: new `src/chatinho/support/kits/model/` (`endpoint.py`, `chat.py`,
  `__init__.py`); `connectors/openai.py`, `routers/llm.py`,
  `support/kits/agent/peer.py` use it; `support/kits/agent/model.py` removed.
- Tests: new `tests/models/`; the stub of `AsyncOpenAI` is patched in the model
  kit instead of in each consumer (`tests/connectors/test_openai_connector.py`,
  `tests/routers/test_llm_router.py`, `tests/test_examples.py`); the
  `AC-CONN-027` tests move to `tests/models/` as `AC-MODEL-003`.
- Packaging: none; the kit needs `openai`, which `chatinho[openai]` and
  `langchain-openai` already bring.
- Assumptions: the router's rotated-out clients are now closed once idle, as the
  connector's were, instead of at shutdown — the stricter of the two rules.
  A component builds its own `EndpointModel` from the `Endpoint` it is given;
  passing one model to several components is left for later.

## Out of Scope

- Components accepting an `EndpointModel` instead of an `Endpoint`.
- Providers other than OpenAI-compatible endpoints.
