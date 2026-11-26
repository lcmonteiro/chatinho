# Review: use-lent-keys-in-agents

Base: `origin/main`

## Findings

- [x] R1 **test-gap** AC-CONN-026.7 passed on the stub: it asked an unreachable port, so the lent key was never sent and nothing could echo it; the test proved nothing about a lent key (`tests/connectors/test_basic_agent_connector.py`, `test_the_lent_key_is_never_shown`)
  - **Decision**: code fixed: the test now runs against `serve_chat(refuses())`, a server answering 401 with the key in its error message as OpenAI's does, asserts the run really sent the lent key, then that the key is in neither the reply, the `repr` nor any record. It fails on the stub (`the run did not use the lent key`).

## Changed files without tags

- `tests/fakes/llm_server.py`: test double for REQ-CONN-026 (a local OpenAI-compatible server that records each request's key); helpers carry no `@ac`.
- `tests/fakes/__init__.py`: lists the new fake in the package docstring.

## Summary

The code follows the spec and the design: the lent key rides in a context
variable set on every run, read by the Endpoint's key function. One test-gap
(AC-CONN-026.7 never failing) was fixed in the test; no spec or design change.
