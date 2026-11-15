# Proposal: baseline-keys

## Why

`keys` has no living spec: what the key sources and the endpoint profiles promise is in two OpenSpec specs and the tests. Recording the existing behaviour lets later changes MODIFY its requirements instead of only adding them.

## What Changes

- No behaviour change. The existing behaviour of `keys` is recorded as 12 requirements, and its existing tests and code gain `@ac` and `@req` tags.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `keys`: gains its first requirements, REQ-KEYS-001 to REQ-KEYS-012, all ADDED.

## Related requirements

None: `spec find` shows no requirement of `framework` about key sources or endpoints.

## Impact

Comment tags in `src/chatinho/support/parts/keys/sources.py` and `endpoint.py`, and in `tests/keys/`. No API, data or dependency changes.

## Out of Scope

- Where a key source is accepted outside this capability (`OpenAIConnector`'s key, the MCP bearer tokens, delegated credentials, and a server token read when the frontend is created): recorded by the baselines of `connectors` and `frontends`.
- No suspected bug was found in the behaviour read.
