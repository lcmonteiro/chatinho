# Tasks: add-logging

## 1. The log file

- [x] 1.1 Add `src/chatinho/logs.py` with `LOG_FORMAT`, `log_file`, `open_log` and `close_log` as stubs, the `open_log()` call at the top of `ChatSession.run()`, and `logs` in `FRAMEWORK` in `tests/test_architecture.py` (REQ-CORE-034); verify `uv run mypy src/chatinho` and `uv run pytest -q tests/test_architecture.py`
- [ ] 1.2 [test] Write failing tests in `tests/framework/test_log_file.py` for AC-CORE-034.1 to AC-CORE-034.6, with `tempfile.tempdir` on `tmp_path` and `close_log()` after each, tagged `@ac`; verify they fail on the stubs, not on imports
- [ ] 1.3 [code] Implement `logs.py`: the file in the temporary directory, the queue and its listener thread, `propagate` off and the forwarding handler with the program's threshold, once per process, the stderr line on failure, `atexit`, `close_log` (REQ-CORE-034) tagged `@req REQ-CORE-034`; verify `uv run ruff check src` and `uv run mypy src/chatinho`, and that `python examples/hooks.py` leaves its lines in `/tmp/chatinho.<today>.log`

## 2. The session's events

- [ ] 2.1 [test] Write failing tests in `tests/framework/test_session_logging.py` for AC-CORE-035.1 to AC-CORE-035.7 and AC-CORE-036.1, AC-CORE-036.2, with `caplog` on `chatinho` at DEBUG, tagged `@ac`; verify they fail for missing records
- [ ] 2.2 [code] Log attach, start, close, post, the ask's outcome, invoke, routing and forget in `session.py`, ids and counts only (REQ-CORE-035, REQ-CORE-036) tagged `@req`; verify `uv run ruff check src`, `uv run mypy src/chatinho`, and that a run of `examples/hooks.py` shows a `posted` line per message and no message text in the file

## 3. The specializations' events

- [ ] 3.1 [test] Write failing tests in `tests/backends/test_backend_logging.py` for AC-BACK-014.1 to AC-BACK-014.3, against a real SQLite archive and a hive served on a free port, tagged `@ac`; verify they fail for missing records
- [ ] 3.2 [code] Log `load`, `forget`, `keep`, `link` in `DatabaseBackend` and `HiveBackend`, and each batch the hive's sender sends (REQ-BACK-014) tagged `@req`; verify `uv run ruff check src` and `uv run mypy src/chatinho`
- [ ] 3.3 [test] Write failing tests in `tests/connectors/test_connector_logging.py` for AC-CONN-025.1 to AC-CONN-025.4, with the stubbed OpenAI client and the MCP fake, tagged `@ac`; verify they fail for missing records
- [ ] 3.4 [code] Log each request of `OpenAIConnector` and `McpConnector` with its duration and outcome, and bring their touched calls to %-style (REQ-CONN-025) tagged `@req`; verify `uv run ruff check src` and `uv run mypy src/chatinho`
- [ ] 3.5 [test] Write failing tests in `tests/agents/test_agent_logging.py` for AC-AGENT-013.1 to AC-AGENT-013.4, with the scripted model, tagged `@ac`; verify they fail for missing records
- [ ] 3.6 [code] Log each run of `AgentPeer` with its duration and outcome, and each build with the factory and the number of tools (REQ-AGENT-013) tagged `@req`; verify `uv run ruff check src` and `uv run mypy src/chatinho`
- [ ] 3.7 [test] Write failing tests in `tests/workspaces/test_worktree_logging.py` for AC-WS-006.1 to AC-WS-006.3, on a real git repository, tagged `@ac`; verify they fail for missing records
- [ ] 3.8 [code] Log each merge and drop of `GitWorktrees`, and a warning when one fails (REQ-WS-006) tagged `@req`; verify `uv run ruff check src` and `uv run mypy src/chatinho`

## 4. Docs

- [ ] 4.1 [code] Describe the log file in `CLAUDE.md` (where it is, what it holds and does not, that only `run()` opens it, the layout's `logs.py`) and `docs/architecture.md` (REQ-CORE-034, REQ-CORE-036); verify `uv run ruff check src tests examples` and `uv run mypy src/chatinho examples`
