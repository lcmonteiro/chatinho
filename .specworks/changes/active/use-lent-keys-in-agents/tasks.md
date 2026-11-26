# Tasks: use-lent-keys-in-agents

## 1. An agent answers with a lent key

- [x] 1.1 Add `credential: str = "llm"` to `AgentPeer.__init__` in `src/chatinho/support/kits/agent/peer.py`, kept as `self.credential` and otherwise unused, and add `tests/fakes/llm_server.py` with `serve_chat` (REQ-CONN-026); verify `ruff check src tests examples` and `mypy src/chatinho examples`
- [ ] 1.2 [test] In `tests/connectors/test_basic_agent_connector.py`, write failing tests tagged `@ac AC-CONN-026.1` to `@ac AC-CONN-026.7` against `serve_chat`: the asker's key then its own; no key of its own; `credential="openai"`; two concurrent questions with `sk-one` and `sk-two`; a second agent asked during the run uses `sk-own`; a ready chat model answers and one warning says the key was ignored; `sk-lent` in neither the failed reply, the `repr` nor any log record (REQ-CONN-026); verify they fail on the stub for the right reason
- [ ] 1.3 [code] Implement REQ-CONN-026 in `peer.py`: a `ContextVar` holding the lent `Secret`, set at the start of every `_run` to the question's `credentials.get(self.credential)` and reset after; `chat_model`'s key function returns it when set and reads the endpoint's source otherwise; one warning when the model is not an `Endpoint` and a key is lent; docstring `Args` updated; tagged `@req REQ-CONN-026`; verify `ruff check src tests examples` and `mypy src/chatinho examples`
