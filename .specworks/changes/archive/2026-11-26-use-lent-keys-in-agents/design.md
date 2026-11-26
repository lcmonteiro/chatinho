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

### The lent key rides in a context variable the key function reads

`peer.py` holds a module-level `ContextVar` `_LENT`. `AgentPeer._run` sets it to
the question's lent `Secret` (or None) before `graph.ainvoke` and resets it after.
The `api_key` function `chat_model` builds returns the lent key when `_LENT`
holds one, and otherwise reads the endpoint's source as today. asyncio copies
the context into every task the run starts, so LangGraph's nodes and the tool
calls see it, and two runs at once each see their own. Serves REQ-CONN-026.

Alternatives: a `ChatOpenAI` per key, cached by the key's digest as
`OpenAIConnector` caches its client — but the model is baked into the agent,
so that means a graph per key, rebuilt by the factory, and a cache to bound and
close; and passing the key in the run's `config`, which only reaches what reads
the config, and the chat model's client does not.

### Every run sets the variable, to a key or to none

A peer the agent asks is delivered in a task the session creates from inside
the agent's run, so it inherits the run's context. Because `_run` always sets
`_LENT` — to None when its own question lends nothing — an agent asked during
another's run never sees that run's key. Serves AC-CONN-026.5.

### A model that is not an Endpoint ignores the key, once out loud

`chat_model` returns any other model as is, so there is nowhere to put a key.
`_run` logs a warning the first time a question lends one, naming the
connector and the credential, never the key. Serves AC-CONN-026.6.

## Interfaces

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

- [The OpenAI client stores the key it read on itself before building each request] -> it does so with no suspension between reading and building, so two runs on one client cannot swap keys; AC-CONN-026.4 drives two concurrent runs against a real server to hold that.
- [A peer started from a run inherits its context] -> `_run` always sets the variable (AC-CONN-026.5).

## Open Questions

None.
