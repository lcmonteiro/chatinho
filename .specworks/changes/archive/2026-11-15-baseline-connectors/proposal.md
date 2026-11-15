# Proposal: baseline-connectors

## Why

`connectors` has no living spec: what the OpenAI, MCP and agent connectors promise is in four OpenSpec specs and the tests. Recording the existing behaviour lets later changes MODIFY its requirements instead of only adding them.

## What Changes

- No behaviour change. The existing behaviour of `connectors` is recorded as 24 requirements, and its existing tests and code gain `@ac` and `@req` tags.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `connectors`: gains its first requirements, REQ-CONN-001 to REQ-CONN-024, all ADDED.

## Related requirements

REQ-AGENT-001 to REQ-AGENT-003 left: they say how `AgentPeer` takes a factory; this change records what an agent connector does in a chat. REQ-KEYS-007 and REQ-KEYS-008 left: the connectors take a key source and an `Endpoint` as those define them. REQ-CORE-025 left: a lent key rides on the message as it says.

## Impact

Comment tags in `src/chatinho/connectors/` (`openai.py`, `mcp.py`, `agents/basic.py`, `agents/deep.py`), in the code of `src/chatinho/support/kits/agent/` and `src/chatinho/support/parts/memory.py` that the agent connectors' behaviour lives in, and in `tests/connectors/`. No API, data or dependency changes.

## Out of Scope

- Where the connectors are imported from and which extra each needs: REQ-CORE-028 already records the names behind an extra.
- What the MCP server does with a lent credential (declaring it, clearing it once the message is answered): recorded by the baseline of `frontends`.
- The terminal asking a connector with `@name`: recorded by the baseline of `frontends`.
- No suspected bug was found in the behaviour read.
