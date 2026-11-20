# Tasks: add-router-headers

## 1. Extra request headers on LLMRouter

- [x] 1.1 Add the `headers` keyword to `LLMRouter.__init__` in `src/chatinho/routers/llm.py`, accepted and ignored, and `default_headers` to `FakeOpenAI.__init__` in `tests/fakes/llm.py`, recorded as `self.default_headers` (REQ-ROUTE-012); verify `specworks run lint`
- [x] 1.2 [test] In `tests/routers/test_llm_router.py`, write failing tests tagged `@ac AC-ROUTE-012.1` to `@ac AC-ROUTE-012.7`: the client built for its own key and for a lent key is given the headers; none for no headers or `{}`; a later change to the caller's dict has no effect; `["X-A"]`, `{"X-A": 1}`, `{1: "x"}` and `{"authorization": ...}` raise `ValueError`, the last naming `authorization` without its value; `tok-secret` in neither `repr` nor a warning after a failed request; verify they fail on the stub for the right reason
- [x] 1.3 [code] Implement REQ-ROUTE-012 in `LLMRouter`: validate and copy `headers` in `__init__` (`ValueError` naming the header, never a value; `authorization` refused ignoring case), keep them as `_headers` (None when empty), and pass `default_headers=self._headers` to the `AsyncOpenAI` built in `_choose` and in `_own_client`, with the docstring's `Args` and `Raises` updated, tagged `@req REQ-ROUTE-012`; verify `ruff check src tests examples` and `mypy src/chatinho examples`
