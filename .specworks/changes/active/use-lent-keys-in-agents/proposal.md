# Proposal: use-lent-keys-in-agents

## Why

A key lent with a question (`msg.credentials`, e.g. by `McpFrontend` for each
MCP client) is ignored by the agent connectors: `BasicAgentConnector` and
`DeepAgentConnector` always call their model with their endpoint's own key.
`OpenAIConnector` already answers with the lent key (REQ-CONN-004), so the same
chat bills a client's key or the owner's depending on which kind of peer
answers, and an agent with no key of its own cannot be used at all by a client
that lends one.

## What Changes

- An agent whose model is an `Endpoint` answers each question with the key lent
  on it under its `credential` name (default `llm`), for that run only, and
  otherwise with its endpoint's key, as today.
- An agent whose endpoint has no key can answer every question that comes with
  one lent.
- Two questions at once, lent different keys, each reach the model with their
  own; a peer the agent asks during a run never inherits the lent key.
- An agent whose model is not an `Endpoint` (a model name or a ready chat model)
  cannot be given a key: it ignores a lent one, as before, and says so once in a
  warning.
- `AgentPeer` (and both connectors) take `credential=`, like `OpenAIConnector`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `connectors`: adds REQ-CONN-026, an agent answers with a key lent on the question.

## Related requirements

- REQ-CONN-004 left: `OpenAIConnector`'s own rule; REQ-CONN-026 mirrors it for agents.
- REQ-CONN-018 left: an `Endpoint` still becomes a chat model reading its key when it is called; with no key lent, everything it says still holds.
- REQ-CONN-012 left: still one run per question; the key is per run.
- REQ-CONN-025 left: about `OpenAIConnector` and `McpConnector` logging.
- REQ-CONN-010 left: `McpConnector` lending onwards is unrelated.
- REQ-CORE-025 left: credentials ride on the message unchanged; this only reads them.
- REQ-CORE-036 left: the session's records are unchanged.
- REQ-FRONT-028 left: how `McpFrontend` lends and clears keys is unchanged.
- REQ-ROUTE-009, REQ-ROUTE-010 left: `LLMRouter`'s lent key is unrelated.

## Impact

- Code: `src/chatinho/support/kits/agent/peer.py` (`chat_model`, `AgentPeer.__init__`, `AgentPeer._run`).
- Tests: `tests/connectors/test_basic_agent_connector.py`, with a local
  OpenAI-compatible server in `tests/fakes/` that records the key each request carries.
- No new dependency; the public API gains one keyword argument.
- Assumptions: the lent key is held for the run in a context variable the
  endpoint's key function reads, so the graph and the client are shared by every
  key and nothing is rebuilt per key; it is set at the start of every run, to
  the lent key or to none, which is what keeps it from reaching a peer the agent
  asks. The error text with no key at all is unchanged.

## Out of Scope

- Lending a key to a model that is not an `Endpoint`.
- Lending to tools the agent was given, or onwards to the peers it asks.
- The other agent gaps (attachments, worktree sharing, interrupts, providers).
