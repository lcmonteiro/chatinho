# Proposal

## Why

`act-on-codebase-review` (merged in [lcmonteiro/chatinho#42](https://github.com/lcmonteiro/chatinho/pull/42)) made `ask()` return the answer's `Reply`, and the agent's chat tools now hand that `Reply` to the model. The `agent-connector` spec still describes the old behaviour: it says a failing peer's tool "returns text saying `coder` failed". The spec should describe what the code and its tests already do.

## What Changes

- The `ask_<peer>` tools and `ask_user` return the asked peer's `Reply`, with its text and status (`answered`, `asked` or `error`), as the tool's result.
- A peer that raises makes its tool return an `error` `Reply` naming the peer and the exception's type, never its message. An error reply the peer returned itself reaches the agent as that `Reply`. Either way the run continues.
- `run_<command>` tools are unchanged: they still return the command's text.
- No code changes. This only brings the spec in line with `src/chatinho/connectors/agent.py` and `tests/test_agent_connector.py` as they are on `main`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `agent-connector`: in "The chat as tools", the `ask_` and `ask_user` tools return the peer's `Reply`, and a failure is an `error` `Reply` rather than text.

## Impact

- **Specs:** `openspec/specs/agent-connector/spec.md` (one requirement, on archive).
- **Code:** none.
- **Docs:** none. CLAUDE.md and `docs/SPEC.md` already describe `ask` returning a `Reply`.
