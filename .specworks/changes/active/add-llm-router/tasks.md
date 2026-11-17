# Tasks: add-llm-router

## 1. A peer describes itself

- [x] 1.1 Extend `connector(name, id=None, description="")` in `src/chatinho/hooks.py` as a stub that accepts the keyword (REQ-CORE-002); verify `uv run mypy src/chatinho` passes
- [ ] 1.2 [test] Write failing tests for AC-CORE-002.6, AC-CORE-002.7, AC-CORE-002.8 in `tests/framework/test_require.py`, tagged `@ac`; verify they fail on the missing description, not on an import
- [ ] 1.3 [code] Set `cls.description` and refuse a non-string with `ValueError` (REQ-CORE-002), tagged `@req REQ-CORE-002`; verify `uv run ruff check src` and `uv run mypy src/chatinho` pass and `@connector("w", description=3)` raises in a REPL

## 2. SimpleRouter's rules as a function

- [x] 2.1 Add `answering(msg, roster)` and `simple_route(msg, roster, context)` to `src/chatinho/routers/simple.py` as stubs (REQ-ROUTE-007); verify `uv run mypy src/chatinho` passes
- [ ] 2.2 [code] Move `SimpleRouter.route`'s body into `simple_route` and `answering`, and have `SimpleRouter.route` call it (REQ-ROUTE-004, REQ-ROUTE-005, REQ-ROUTE-007), tagged `@req`; verify `uv run ruff check src` and `uv run mypy src/chatinho` pass and the module imports nothing but the framework

## 3. LLMRouter: when the model is asked

- [x] 3.1 Add `src/chatinho/routers/llm.py` with `ROUTING_MEMORY`, `EVERYONE` and `LLMRouter` (`__init__`, `route`, `shutdown`) as stubs that route nothing, `AsyncOpenAI` imported at module level (REQ-ROUTE-007, REQ-ROUTE-008, REQ-ROUTE-009, REQ-ROUTE-010); verify `uv run mypy src/chatinho` passes
- [ ] 3.2 [test] Write failing tests for AC-ROUTE-007.1, AC-ROUTE-007.2, AC-ROUTE-007.3, AC-ROUTE-007.4 in `tests/routers/test_llm_router.py` with `tests/fakes/llm.FakeOpenAI` patched in, tagged `@ac`; verify they fail on the stub's behaviour
- [ ] 3.3 [code] Route by `simple_route` first, and ask the model only when it finds nobody and `answering` holds two or more (REQ-ROUTE-007), tagged `@req REQ-ROUTE-007`; verify `uv run ruff check src` and `uv run mypy src/chatinho` pass

## 4. LLMRouter: what the model is told and how it is read

- [ ] 4.1 [test] Write failing tests for AC-ROUTE-008.1, AC-ROUTE-008.2, AC-ROUTE-008.3, AC-ROUTE-008.4, AC-ROUTE-008.5 in `tests/routers/test_llm_router.py`, reading the request the fake recorded, tagged `@ac`; verify they fail on the stub's behaviour
- [ ] 4.2 [code] Build the prompt from the candidates' names and descriptions, the earlier messages `memory` selects (`support/parts/memory.earlier`) and the say, and read the answer as one normalised name or `everyone` (REQ-ROUTE-008), tagged `@req REQ-ROUTE-008`; verify `uv run ruff check src` and `uv run mypy src/chatinho` pass

## 5. LLMRouter: failures and keys

- [ ] 5.1 [test] Write failing tests for AC-ROUTE-009.1, AC-ROUTE-009.2, AC-ROUTE-009.3, AC-ROUTE-009.4, AC-ROUTE-009.5, AC-ROUTE-009.6, AC-ROUTE-010.1, AC-ROUTE-010.2 in `tests/routers/test_llm_router.py`, with `caplog` for the warnings, tagged `@ac`; verify they fail on the stub's behaviour
- [ ] 5.2 [code] Run the choice under `asyncio.wait_for(timeout)`, turn an unknown or shared name, an API error, an `OSError`, `KeyUnavailable` and a timeout into a warning and None without the say's text or a key, and refuse a non-positive timeout (REQ-ROUTE-009), tagged `@req REQ-ROUTE-009`; verify `uv run ruff check src` and `uv run mypy src/chatinho` pass
- [ ] 5.3 [code] Use a key lent as `credential` for that say alone, else its endpoint's key read late, keeping one own client per key digest and closing every kept client at `shutdown` (REQ-ROUTE-010), tagged `@req REQ-ROUTE-010`; verify `uv run ruff check src` and `uv run mypy src/chatinho` pass

## 6. Where LLMRouter is imported from

- [x] 6.1 Add `LLMRouter` to `routers/__init__.py` (a PEP 562 `__getattr__`) and to the root's `_BEHIND_AN_EXTRA`, `TYPE_CHECKING` block and `__all__`, as stubs (REQ-ROUTE-011); verify `uv run mypy src/chatinho` passes
- [ ] 6.2 [test] Write failing tests for AC-ROUTE-011.1, AC-ROUTE-011.2, AC-ROUTE-011.3 in `tests/routers/test_llm_router_imports.py`, the blocked-import ones in a subprocess, tagged `@ac`; verify they fail for the right reason
- [ ] 6.3 [code] Resolve `LLMRouter` lazily from both packages, naming `chatinho[openai]` when `openai` is missing (REQ-ROUTE-011), tagged `@req REQ-ROUTE-011`; verify `python -c "import chatinho.routers"` with `openai` blocked imports, and `uv run mypy src/chatinho` passes

## Workflow follow-up

- At close: CLAUDE.md's public API count (82 → 83), its battery table (`LLMRouter` behind `chatinho[openai]`) and the `routers/` line of its layout.
