# Proposal

## Why

`McpFrontend` hands an MCP client the *first* reply to its question, from anyone. A peer that listens and replies to a question it overheard therefore ends the client's call with its own text. Reproduced on `main`: a client asking `weather` (which answers after 0.2 s) received a bystander's `"not my question"` instead of `"sunny"`.

The session already holds its own `ask` to the rule that only the asked peer's reply resolves it (`message-delivery`, "Only the asked peer resolves an ask"). The MCP frontend speaks with `say(text, to=peer)` and matches replies in `listen`, so that rule never reaches it. An earlier fix kept the asked peer on each open question; it was reverted at review in [lcmonteiro/chatinho#42](https://github.com/lcmonteiro/chatinho/pull/42).

## What Changes

- `McpFrontend` ends a client's call only with a reply from the peer the question was asked of. A reply from anyone else is overheard and ignored, and the call keeps waiting.
- Who was asked is read from the conversation, not stored again. The frontend declares `HookContext` and looks up the question's `asked_of`, which the session already records on every message it posts.
- The replies the session posts in the asked peer's name (the error reply when its `answer` raises, and the "too many nested asks" reply) still end the call, because they are posted as that peer.
- If the question can no longer be found (dropped by `forget()` while it was open), the first reply ends the call, as today. That way a call never waits forever on a question nobody can find.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `mcp-server`: in "The frontend speaks for every client", only the asked peer's reply ends a client's call.

## Impact

- **Code:** `src/chatinho/frontends/mcp.py`: `McpFrontend` gains `@require(HookContext)` and a `context` annotation, and `listen` checks the reply's sender.
- **Tests:** a regression test in `tests/test_mcp_frontend.py` that fails on `main`.
- **Docs:** one sentence in CLAUDE.md's "Answering late" paragraph saying `McpFrontend` follows the same rule.
- **API:** none. The MCP tools and their results are unchanged for a client whose question is answered by the peer it asked.
