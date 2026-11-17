# Tasks: clean-failing-peer-test

## 1. The failing peer of the MCP ask test

- [ ] 1.1 [test] In `tests/frontends/test_mcp_frontend.py`, declare a local `@connector("weather")` peer whose `answer` raises `RuntimeError("boom")`, and make `test_a_failing_peer_is_an_error` ask it instead of `Weather(RuntimeError(...))` with an `answer` patched through `session._peers()`; keep its `@ac` tag (the frontends criterion on a failing peer) and its assertions (status `error`, `failed` in the text); verify with `uv run pytest -q tests/frontends/test_mcp_frontend.py` and `grep -n "_peers()\[1\]" tests/frontends/test_mcp_frontend.py` finding nothing
