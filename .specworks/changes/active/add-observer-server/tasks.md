# Tasks: add-observer-server

## 1. Traces in the framework

- [ ] 1.1 Add `TRACE_TEXT_LIMIT`, `TraceState`, `TraceID`, `ChatTrace` to `message.py`, `HookTrace`, `HookRecord` and the `Trace` protocol to `hooks.py`, the `trace` grant stub in `session.py`, and the new names to `chatinho/__init__.py` (REQ-CORE-030, REQ-CORE-033); verify `uv run mypy src/chatinho` passes
- [ ] 1.2 [test] Write failing tests in `tests/framework/test_traces.py` for AC-CORE-030.1 to AC-CORE-030.7, AC-CORE-031.1, AC-CORE-031.2, AC-CORE-032.1 to AC-CORE-032.4 and AC-CORE-033.1, AC-CORE-033.2, tagged `@ac`; verify they fail on the stubs, not on imports
- [ ] 1.3 [code] Implement the trace record, `TraceID.new`/`parse`, and `ChatSession._trace`: checks, cutting, numbering, handing to the first `HookRecord` declarer, logging its failure (REQ-CORE-030, REQ-CORE-031, REQ-CORE-032) tagged `@req`; verify `uv run ruff check src` and `uv run mypy src/chatinho`
- [ ] 1.4 [code] Add the `HookTrace` and `HookRecord` sections and table rows to `docs/SPEC.md`, nineteen hooks (REQ-CORE-033) tagged `@req` on the constants; verify `docs/SPEC.md` names both hooks with their grant and method

## 2. The wire format

- [ ] 2.1 Add `support/parts/hive.py` with `KEY_HEADER` and the four `*_to_wire`/`*_from_wire` functions as stubs (REQ-BACK-009, REQ-HIVE-004, REQ-HIVE-005); verify `uv run mypy src/chatinho`
- [ ] 2.2 [code] Implement the wire functions, round-tripping every field and raising `ValueError` on a malformed payload (REQ-BACK-009, REQ-HIVE-004, REQ-HIVE-005) tagged `@req`; verify `python -c` round trip of a message and a trace prints equal records

## 3. The hive

- [ ] 3.1 Add `hive/__init__.py`, `app.py`, `keys.py`, `store.py`, `live.py`, `cli.py` and `page.html` as stubs, the `hive` extra, the `chatinho-hive` script, package data, `hive` in the architecture test's specializations, and `uv lock` (REQ-HIVE-001 to REQ-HIVE-010); verify `uv sync --extra dev` and `uv run chatinho-hive --help`
- [ ] 3.2 [test] Write failing tests in `tests/hive/test_hive_keys.py` for AC-HIVE-001.1 to AC-HIVE-001.5, AC-HIVE-002.1, AC-HIVE-002.2, tagged `@ac`; verify they fail on the stubs
- [ ] 3.3 [test] Write failing tests in `tests/hive/test_hive_api.py` for AC-HIVE-003.1 to AC-HIVE-003.4, AC-HIVE-004.1 to AC-HIVE-004.4, AC-HIVE-005.1 to AC-HIVE-005.4, AC-HIVE-006.1 to AC-HIVE-006.4, AC-HIVE-009.1, tagged `@ac`; verify they fail on the stubs
- [ ] 3.4 [test] Write failing tests in `tests/hive/test_hive_live.py` for AC-HIVE-007.1 to AC-HIVE-007.3, tagged `@ac`; verify they fail on the stubs
- [ ] 3.5 [test] Write failing tests in `tests/hive/test_hive_page.py` for AC-HIVE-008.1 and, with Playwright when it can be imported, AC-HIVE-008.2, tagged `@ac`; verify they fail on the stubs
- [ ] 3.6 [test] Write failing tests in `tests/hive/test_hive_install.py` for AC-HIVE-010.1 to AC-HIVE-010.3, tagged `@ac`; verify they fail on the stubs
- [ ] 3.7 [code] Implement keys, the store and the CLI's `chat` and `admin` commands (REQ-HIVE-001, REQ-HIVE-002) tagged `@req`; verify `chatinho-hive chat add team --db sqlite:///<tmp>` prints a key and `chat list` shows `team`
- [ ] 3.8 [code] Implement the app: key checks, the chat and admin routes, resends, 401/403/404/422 (REQ-HIVE-003 to REQ-HIVE-006, REQ-HIVE-009) tagged `@req`; verify `curl` on a running hive answers 401 with no key and 200 on `/openapi.json`
- [ ] 3.9 [code] Implement `Live` and the stream route (REQ-HIVE-007) tagged `@req`; verify `curl -N .../stream?key=` shows an event when a message is posted
- [ ] 3.10 [code] Implement the viewer page (REQ-HIVE-008) tagged `@req` in `app.py`; verify by opening it on a running hive with a chat and traces
- [ ] 3.11 [code] Implement `serve` and the extra's `ImportError` (REQ-HIVE-010) tagged `@req`; verify `uv run chatinho-hive serve --port 8711` answers on `/`

## 4. HiveBackend

- [ ] 4.1 Add `backends/hive.py` (`HiveBackend`, `HiveUnavailable`) and `backends/hive_cache.py` (`HiveCache`, `Outbox`) as stubs (REQ-BACK-009 to REQ-BACK-013); verify `uv run mypy src/chatinho`
- [ ] 4.2 [test] Write failing tests in `tests/backends/test_hive_backend.py`, against a hive served on a free port, for AC-BACK-009.1 to AC-BACK-009.6 and AC-BACK-010.1 to AC-BACK-010.3, tagged `@ac`; verify they fail on the stubs
- [ ] 4.3 [test] Write failing tests in `tests/backends/test_hive_offline.py` for AC-BACK-011.1 to AC-BACK-011.7 and AC-BACK-012.1, AC-BACK-012.2, tagged `@ac`; verify they fail on the stubs
- [ ] 4.4 [test] Write failing tests in `tests/backends/test_hive_cache.py` for AC-BACK-013.1 to AC-BACK-013.6, tagged `@ac`; verify they fail on the stubs
- [ ] 4.5 [code] Implement HTTP off the loop, `load`, `forget`, `keep`, `link`, `record` and the speaker's name (REQ-BACK-009, REQ-BACK-010) tagged `@req`; verify a script saying to a running hive shows the message in `GET /api/chats/<name>/messages`
- [ ] 4.6 [code] Implement the outbox, the sender's order, batches, backoff, limit, flush at shutdown and refused keys (REQ-BACK-011, REQ-BACK-012) tagged `@req`; verify a script with the hive stopped and then started delivers in order
- [ ] 4.7 [code] Implement the cache: mirror, persisted outbox, offline `load` and `link`, `forget`, the URL check (REQ-BACK-013) tagged `@req`; verify a script restarted with the hive down shows its history

## 5. AgentPeer traces its runs

- [ ] 5.1 Add `support/kits/agent/tracing.py` (`RunTracer`) as a stub and declare `HookTrace` on `AgentPeer` (REQ-AGENT-012); verify `uv run mypy src/chatinho`
- [ ] 5.2 [test] Write failing tests in `tests/agents/test_agent_tracing.py` for AC-AGENT-012.1 to AC-AGENT-012.6 with the scripted model, tagged `@ac`; verify they fail on the stub
- [ ] 5.3 [code] Implement `RunTracer` and pass one per run in `AgentPeer._run`'s config (REQ-AGENT-012) tagged `@req`; verify `examples/agent.py`-style run with a recorder prints the node traces

## 6. Docs and examples

- [ ] 6.1 [code] Update `CLAUDE.md` (nineteen hooks, the hive, the extra, 92 names, layout), `docs/architecture.md` (the hive, traces) and `examples/README.md` with a hive example (REQ-HIVE-010, REQ-CORE-033); verify `uv run ruff check src tests examples` and `uv run mypy src/chatinho examples`

## Workflow follow-up

- Register the capability at close: `specworks capability add hive --path src/chatinho/hive`.
