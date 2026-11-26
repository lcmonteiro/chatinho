# Tasks: share-the-endpoint-model

## 1. The shared model

- [x] 1.1 Create `src/chatinho/support/kits/model/` with `EndpointModel` and `lent_key` as stubs in `endpoint.py`, move `EndpointChatModel` to `chat.py` unchanged (its `@req REQ-CONN-027` tag becoming `REQ-MODEL-003`), and export them from `__init__.py` (REQ-MODEL-001, REQ-MODEL-002, REQ-MODEL-003, REQ-MODEL-004, REQ-MODEL-005); verify `ruff check src tests examples` and `mypy src/chatinho examples`
- [x] 1.2 [test] Write `tests/models/test_endpoint_model.py`, failing on the stubs, tagged `@ac AC-MODEL-001.1` to `@ac AC-MODEL-001.5`, `@ac AC-MODEL-002.1` to `@ac AC-MODEL-002.3`, `@ac AC-MODEL-004.1`, `@ac AC-MODEL-005.1` (a subprocess with LangChain blocked) and `@ac AC-MODEL-006.1` (parsing `src/chatinho`), with `FakeOpenAI` patched over the kit's `AsyncOpenAI`; move the `AC-CONN-027` tests out of `tests/connectors/test_basic_agent_connector.py` into `tests/models/test_endpoint_chat_model.py` as `@ac AC-MODEL-003.1` to `.5`, removing REQ-CONN-027 from the tests (REQ-MODEL-001..006, REQ-CONN-027); verify they fail for the right reason
- [x] 1.3 [code] Implement `EndpointModel` (own client per key digest with a use count, rotated-out closed once idle, a client per call for `api_key`, headers on both, `KeyUnavailable` with no key, `close()`), `lent_key`, and `chat_model()` importing `chat.py` lazily with an `ImportError` naming `chatinho[langchain]`; make `EndpointChatModel` take its `EndpointModel`; tagged `@req`; verify `ruff check src tests examples` and `mypy src/chatinho examples`

## 2. Every component through it

- [x] 2.1 [test] Patch `FakeOpenAI` over the model kit's `AsyncOpenAI` in `tests/connectors/test_openai_connector.py`, `tests/routers/test_llm_router.py` and `tests/test_examples.py`, keeping every assertion (REQ-MODEL-006); verify the connector and router tests fail before 2.2 for the right reason (the real client is used)
- [x] 2.2 [code] Make `OpenAIConnector`, `LLMRouter` and `AgentPeer` build an `EndpointModel` and call it with `lent_key(msg, self.credential)`; remove their own clients and `support/kits/agent/model.py` (REQ-MODEL-006); verify `ruff check src tests examples` and `mypy src/chatinho examples`
