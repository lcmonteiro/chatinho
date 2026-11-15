# Proposal: baseline-agents

## Why

`agents` has no living spec: what `AgentPeer`, its factories and `WorkspaceBackend` promise is in two OpenSpec specs and the tests. Recording the existing behaviour lets later changes MODIFY its requirements instead of only adding them.

## What Changes

- No behaviour change. The existing behaviour of `agents` is recorded as 11 requirements, and its existing tests and code gain `@ac` and `@req` tags.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `agents`: gains its first requirements, REQ-AGENT-001 to REQ-AGENT-011, all ADDED.

## Related requirements

REQ-WSM-001 to REQ-WSM-010 left: the backend and the `ws_` tools go through those operations and do not change them. REQ-CORE-027 left: the peer's workspace comes from that grant.

## Impact

Comment tags in `src/chatinho/support/kits/agent/` (`peer.py`, `factory.py`, `tools.py`, `workspace_backend.py`, `__init__.py`), in `tests/agents/` and in `tests/test_architecture.py`. No API, data or dependency changes.

## Out of Scope

- What an agent peer does in a chat as seen through the connectors (one run per question, failures as `ERROR` replies, the `ask_`/`run_`/`ws_` tools in use, memory from `context()`, attachments, the link check, a run interrupted for a decision): its tests are the connectors' (`tests/connectors/test_basic_agent_connector.py`, `test_deep_agent_connector.py`), so the baseline of `connectors` records it.
- `WorkspaceBackend` read off `chatinho` without the `deepagents` extra: no test in this capability shows it; the names behind an extra are REQ-CORE-028.
- No suspected bug was found in the behaviour read.
