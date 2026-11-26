# Design: use-lent-keys-in-agents

## Context

`AgentPeer` turns an `Endpoint` into a `ChatOpenAI` once, in `chat_model`, with
an async `api_key` function that reads the endpoint's key source each time the
model is called (REQ-CONN-018). The factory then builds the agent around that
one model, and the compiled graph is cached until the chat's shape changes.
A lent key is on the question (`msg.credentials`), known only when a run starts.

## Goals / Non-Goals

**Goals:**
- One run uses its question's lent key; nothing else does (REQ-CONN-026).

**Non-Goals:**
- Rebuilding the agent, the graph or a client per key.
- Lending a key to a model chatinho did not build.

## Decisions

### The lent key reaches the model as a parameter of a wrapper chat model

`chat_model` turns an `Endpoint` into an `EndpointChatModel`
(`src/chatinho/support/kits/agent/model.py`), a `BaseChatModel` that keeps
LangChain's call interface and adds one keyword, `api_key: Optional[Secret]`.
Its `ainvoke`/`astream` resolve the key — the parameter, else
`configurable["api_key"]` of the run's configuration, else none — and pass it
down to `_agenerate`/`_astream`, which delegate to a `ChatOpenAI` for that key:
the one built once with the endpoint's key function when there is none, or one
built for the call when there is, and dropped with it. `bind_tools` takes the
`ChatOpenAI`'s formatting of the tools and binds it to the wrapper, so a bound
model still goes through the wrapper. Serves REQ-CONN-027.

`create_agent` calls the model itself, with no config of its own, so nothing in
the chat can add a parameter at that call; LangChain hands the node's config to
it, which is why `AgentPeer._run` puts the question's key (a `Secret`, never a
string, so LangChain does not copy it into a run's metadata) in
`configurable["api_key"]`. Serves REQ-CONN-026.

Alternatives: the first round's module-level `ContextVar` read by the key
function — rejected by the person: a hidden global the model depends on;
`ChatOpenAI.configurable_fields` — a `RunnableConfigurableFields` is not a
`BaseChatModel`, which `create_agent` requires; a `ChatOpenAI` cached per key —
keeps lent keys in memory after their question, for a construction that costs
little (the HTTP client is LangChain's shared one).

### Every run sets the key in its configuration, to a key or to none

A peer the agent asks is run from inside the agent's run, and LangChain merges
the running config into the one the peer's graph starts with. Because `_run`
always passes `configurable["api_key"]` — None when its own question lends
nothing — the peer's own configuration replaces the asker's, and an agent asked
during another's run never sees that run's key. Serves AC-CONN-026.5.

### A model that is not an Endpoint ignores the key, once out loud

`chat_model` returns any other model as is, so there is nowhere to put a key.
`_run` logs a warning the first time a question lends one, naming the
connector and the credential, never the key. Serves AC-CONN-026.6.

## Interfaces

- `src/chatinho/support/kits/agent/model.py`: `EndpointChatModel(endpoint: Endpoint)`, a
  `BaseChatModel`: `await ainvoke(input, config=None, *, api_key: Optional[Secret] = None, **kwargs)`,
  `astream(...)` likewise, `bind_tools(tools, **kwargs)`; `invoke`/`stream` raise
  `NotImplementedError` (REQ-CONN-027). `chat_model(endpoint)` in `src/chatinho/support/kits/agent/peer.py` returns one.
- `src/chatinho/support/kits/agent/peer.py`: `AgentPeer.__init__(..., credential: str = "llm", ...)`,
  kept as `self.credential`; keyword-only, beside `memory` (REQ-CONN-026).
  `BasicAgentConnector` and `DeepAgentConnector` pass it through `**options`
  unchanged, so neither signature changes.
- `tests/fakes/llm_server.py`: `serve_chat(answer="...")`, an async context
  manager serving an OpenAI-compatible `/v1/chat/completions` on a free local
  port, yielding an object with `base_url` and `keys`, the bearer key of each
  request in order.

## Diagrams

No structural change.

## Risks / Trade-offs

- [The wrapper hides `ChatOpenAI` from `create_agent`'s OpenAI checks, so a `response_format` uses the tool strategy rather than the provider's] -> the answer is the same; noted in the docstring.
- [A peer started from a run inherits its config] -> `_run` always sets `configurable["api_key"]` (AC-CONN-026.5).
- [A client per call with a lent key] -> cheap: LangChain shares the HTTP client; the endpoint's own key keeps its one client.

## Open Questions

None.
