# Tasks

"The checks" means `ruff check src tests examples`, `mypy src/chatinho examples` and `pytest -q`, all from the repo root.

## 1. Only the asked peer's reply ends a client's call

- [x] 1.1 Add a regression test to `tests/test_mcp_frontend.py`. A client asks `Weather("sunny", delay=0.2)` in a session that also has a listening peer, which says a reply to every question it overhears. The client's result must be `"sunny"`. Verify that it **fails** on the current code (it gets the bystander's text).
- [x] 1.2 Give `McpFrontend` `@require(HookContext)` and a `context : Context` annotation. In `listen`, after the existing guards, look the question up with `context()` and return without ending the call when `msg.frm` is not its `asked_of`. When the question isn't found, keep today's behaviour (design Decisions 1–2). Verify that 1.1 passes, and that `test_a_failing_peer_is_an_error`, `test_two_clients_at_once` and the rest of `tests/test_mcp_frontend.py` pass unchanged.
- [x] 1.3 Add a test that a question dropped by `forget()` while its call is open still ends with the first reply (design Decision 2). Verify it passes.
- [x] 1.4 In CLAUDE.md's "Answering late" paragraph, add that `McpFrontend` holds its open questions to the same rule, reading who was asked from the conversation. Verify the checks pass.

## 2. Integration

- [x] 2.1 Run the checks and `openspec validate --all --strict --no-interactive`. All must pass, and the reproduction (`scratchpad/repro_mcp.py`) must now print `'sunny'`.
