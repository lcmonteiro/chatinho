# Tasks

This change only corrects the spec: the behaviour it describes is already on `main`. "The checks" means `ruff check src tests examples`, `mypy src/chatinho examples` and `pytest -q`, all from the repo root.

## 1. Confirm the spec matches the code

- [ ] 1.1 Map each changed or added scenario to the existing test that proves it, and record the mapping here. "Asking another peer" → `test_asking_another_peer`; "A failing peer" → `test_a_failing_peer`; "A peer's error reply" → `test_a_peers_error_reply_reaches_the_model_as_a_failure`; `ask_user` returning the user's `Reply` → `test_ask_user_when_asked_for` (all in `tests/test_agent_connector.py`). Verify by running `pytest -q tests/test_agent_connector.py -k "asking_another_peer or failing_peer or error_reply or ask_user_when_asked_for"`, which must pass.
- [ ] 1.2 Confirm `AgentConnector._asking` in `src/chatinho/connectors/agent.py` returns the peer's `Reply`, and an `error` `Reply` naming the peer and the exception's type when the peer raises. If it doesn't, stop and report the mismatch instead of changing the code or the spec. Verify by reading the function.

## 2. Integration

- [ ] 2.1 Run the checks and `openspec validate --all --strict --no-interactive`. All must pass.
