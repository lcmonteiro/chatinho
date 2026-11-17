# Refinement: clean-failing-peer-test

## Problem

The test of AC-FRONT-025.5 (`tests/frontends/test_mcp_frontend.py::test_a_failing_peer_is_an_error`) builds its failing peer in two overlapping ways: `Weather(RuntimeError("boom"))` returns the exception as its reply, which the session already treats as a failure (`TypeError`, not a `Reply`), and then the test replaces that peer's `answer` with one that raises, reaching it through the private `session._peers()[1]`. It passes, but it depends on the peer's id and on a private method, and it is unclear which of the two failures it checks. The review and validate of `strengthen-weak-tests` noted it for a later change.

## Outcomes

- None: only a test changes. The criterion AC-FRONT-025.5 keeps its wording and the library its behaviour.

## Context

**Observed:**

- `tests/frontends/test_mcp_frontend.py:66-75`: the test, tagged `@ac AC-FRONT-025.5`, asserts the result's status is `error` and its text contains `failed`.
- `tests/fakes/mcp.py:44-58`: `Weather(reply)` returns `reply` as given unless it is a string; no other test passes it an exception.
- AC-FRONT-025.5 (`src/chatinho/frontends/docs/spec.md`): WHEN the asked peer's `answer` raises, THEN the result is a tool error saying what failed.
- Five other places read `session._peers()` to check the roster (`test_mcp_frontend.py:20,115,119`, `test_workspaces_in_session.py:66`, `test_package_layout.py:75,87,88`); none changes a peer.

**Assumed:**

- A peer declared in the test with `@connector("weather")` and an `answer` that raises takes the same path as the patched one: the session posts `weather failed: RuntimeError` and the MCP `ask` returns it as a tool error.

## Constraints

- [hard] No change to library behaviour, to AC-FRONT-025.5 or to its tag.
- [hard] The shared fakes in `tests/fakes/` stay as they are.
- [soft] Match the local test-peer style already used in the file (`_Mute`, `_Echo`).

## Options

### Option A: a local peer that raises

A small `@connector("weather")` class in the test file whose `answer` raises `RuntimeError("boom")`; the test asks it, with no `_peers()` and no patch.

- **Pros:** the test shows what it tests; nothing shared changes.
- **Cons:** one more local class in the file.
- **Effort:** S
- **Touches:** tests of `frontends` only
- **Outcomes:** meets it (none visible); checks the raising path the criterion names.

### Option B: `Weather` learns to raise

`Weather` raises when given an exception instead of returning it.

- **Pros:** the test stays one line shorter.
- **Cons:** changes a fake many tests use.
- **Effort:** S
- **Touches:** `tests/fakes/mcp.py`, tests of `frontends`
- **Outcomes:** meets it.

### Option C: drop only the patch

Keep `Weather(RuntimeError(...))`, which returns a non-`Reply`.

- **Pros:** smallest diff.
- **Cons:** the peer no longer raises: it checks the `TypeError` path, not what AC-FRONT-025.5 says.
- **Effort:** S
- **Touches:** tests of `frontends` only
- **Outcomes:** fails the criterion's WHEN.

## Recommendation

Option A, chosen by the user: the test names its own failing peer and checks the path its criterion describes, without touching shared fakes. Scope is this one test; the five read-only `_peers()` uses stay, chosen by the user, since nothing public reads the roster without a spy peer.

## Open Questions

- None.

## Candidate Capabilities

- None: no behaviour changes, so the change is marked `specworks skip-specs` (the test touched belongs to `frontends`).
