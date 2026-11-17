# Proposal: clean-failing-peer-test

## Why

The test of AC-FRONT-025.5 builds its failing peer twice over (a `Weather` that returns an exception, then an `answer` patched through the private `session._peers()[1]`), so it depends on a peer id and a private method and does not say which failure it checks. Noted by the review and validate of `strengthen-weak-tests`; option A of the refinement.

## What Changes

- `tests/frontends/test_mcp_frontend.py::test_a_failing_peer_is_an_error` asks a peer declared in the test file whose `answer` raises `RuntimeError`, instead of `Weather(RuntimeError(...))` with a patched `answer`. It keeps its `@ac AC-FRONT-025.5` tag and its assertions (status `error`, `failed` in the text).
- No library code, criterion or shared fake changes.

## Capabilities

### New Capabilities

- None

### Modified Capabilities

- None: no behaviour changes, so the change is marked `specworks skip-specs`. The test belongs to `frontends`.

## Related requirements

- REQ-FRONT-025 left: AC-FRONT-025.5 already says what the test checks once it asks a peer that raises; only how the test builds that peer changes
- REQ-CONN-016 left: the agent's `ask_` tool on a failing peer, matched on "failing peer"; its test is not touched

## Impact

- `tests/frontends/test_mcp_frontend.py` only.

## Out of Scope

- The five read-only uses of `session._peers()` in tests (`test_mcp_frontend.py:20,115,119`, `test_workspaces_in_session.py:66`, `test_package_layout.py:75,87,88`): they only check the roster, which nothing public reads without a spy peer.
- `tests/fakes/mcp.py`: `Weather` is unchanged.
