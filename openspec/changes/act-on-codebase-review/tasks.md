# Tasks

Each group lands its own tests and documentation. "The checks" means `ruff check src tests examples`, `mypy src/chatinho examples` and `pytest -q`, all from the repo root.

## 1. The terminal's notices leave the conversation

- [x] 1.1 Add a regression test to `tests/test_chat_frontend.py`: a chat with one answering peer and `welcome_message="Welcome"`, where the user runs `/nope`. The peer's `answer` must never be called and the conversation must be empty. Verify that it **fails** on the current code.
- [x] 1.2 Give `ChatLog` an optional `banner` (a muted `Static`, class `chat-banner`, mounted once above the messages and outside `sync()`'s window), styled in `ChatStyle.to_css()`. `ChatFrontend.on_mount` passes `welcome_message` to it instead of saying it. Verify with 1.1, and with `test_the_welcome_message_is_the_app_saying_it` rewritten to assert the banner shows the text and `app.messages == []`.
- [x] 1.3 Report an unknown command with `self.notify(..., severity="warning")` and a failed command with `self.notify(..., severity="error")`, instead of `say`. Verify by rewriting the two "Unknown command" assertions (`test_chat_frontend.py:349`, `test_command_suggestions.py:171`) to check the notification with notifications enabled, and the failed-command test likewise. Run 1.1 again; it now passes.
- [x] 1.4 In CLAUDE.md, state that the welcome is a banner and that notices are toasts, never messages. Verify the checks pass.

## 2. Asks are resolved by the asked peer, and ids are unique

- [x] 2.1 Add the two regression tests to `tests/test_chat_session.py`. A bystander that replies to a question first must not resolve the `ask`. A peer declaring `id=1` followed by an unnumbered peer must get ids 1 and 2. Verify that both **fail** on the current code.
- [x] 2.2 In `ChatSession._post`, resolve a waiting ask only when `msg.frm` is the question's `asked_of`, keeping it in `_pending` otherwise (design Decision 1). Verify the first test of 2.1 passes, and that `ask(LOCAL)` answered by the user still resolves (existing tests).
- [x] 2.3 In `add_connector`, skip `_next_id` past taken ids (design Decision 2). Verify the second test of 2.1 passes, and that a duplicate pinned id still raises `ValueError` (existing test).
- [x] 2.4 In `McpFrontend`, remember the addressed peer id on `_Message`, and have `listen` ignore replies from any other peer. Verify with a new test in `tests/test_mcp_frontend.py` (`Another peer replies first`) that fails before the change and passes after.
- [x] 2.5 Add both rules to CLAUDE.md ("Everyone is a peer" and "Three verbs"), and fix the stale `_drain` comment in `session.py`. Verify the checks pass.

## 3. `ask` raises `PeerError` on an error answer

- [ ] 3.1 Add tests to `tests/test_answer_details.py`. `ask` of a peer returning `Reply("quota exceeded", status="error")` raises `PeerError("quota exceeded")`, and the reply is still in the conversation. A `status="asked"` answer returns its text. In `tests/test_message_delivery.py`, `ask` past `max_depth` raises `PeerError`. Verify they fail on the current code.
- [ ] 3.2 Define `PeerError` in `message.py` and export it from `chatinho` (66 names; update `__all__` and the export-count test if one exists). Resolve pending asks with the answering `ChatMessage`, and unwrap it in `ask` (design Decision 3). Verify that 3.1 passes.
- [ ] 3.3 In `AgentConnector._asking`, format `PeerError` with its text and other exceptions by type name only. Verify with a test in `tests/test_agent_connector.py` where a peer's `error` reply reaches the model as `"<name> failed: quota exceeded"`.
- [ ] 3.4 Check the other two callers, `examples/inbox.py:96` (asks the user, who cannot answer `error`) and `examples/hooks.py:296` (asks a peer that answers `sunny`). Neither needs a change unless the checks say otherwise. Verify that `tests/test_examples.py` passes.
- [ ] 3.5 Update the `Ask` protocol docstring in `hooks.py`, the `HookAsk` section of `docs/SPEC.md`, and the "Three verbs" section and public-API count in CLAUDE.md. Verify that `tests/test_architecture.py` (the SPEC check) and the other checks pass.

## 4. The archive keeps `status`

- [ ] 4.1 Add tests to `tests/test_database_backend.py`. An `error` reply reloads with `status` `error` and is left out by `Query(errors=False)`. A database created with the old schema (a `messages` table without `status`, built with raw SQL) opens, and loads its rows as `answered`. Verify that both fail on the current code.
- [ ] 4.2 Add the `status` column, write and read it, and add it in place in `initialize()` when the table lacks it (design Decision 4). Verify that 4.1 passes, and that `scratchpad/repro_db.py`-style behaviour holds: `errors=False` gives the same result before and after a restart.
- [ ] 4.3 Remove `**kwargs` and `self.config` from `DatabaseBackend.__init__`. Verify with a test that `DatabaseBackend("sqlite://", ecoh=True)` raises `TypeError`, and grep `examples` and `tests` for extra keyword arguments to it.
- [ ] 4.4 Update the "status … Not kept by the archive" wording in `ChatMessage`'s docstring, and update CLAUDE.md's archive policy (a column with a safe default is added in place; nothing else is migrated). Verify the checks pass.

## 5. Stale documentation

- [ ] 5.1 Correct the stale docstrings and comments:
  - `hooks.py`: the module docstring's `answer(msg, text)` and "spoke to everyone"; `HookInvoke` (`run`, "nothing … enters the conversation"); `HookExecute` ("goes to whoever ran it"); `HookPeers` (`load_messages`); and `tool()` ("a tool is a peer… a command is an ask").
  - `builder.py`: `save_data`/`load_data`.
  - `composer.py`: the Shift+Enter claim.

  Verify with `grep -rn "save_data\|load_data\|answer(msg, text)\|run(name, args)\|is an ask addressed\|load_messages" src` returning nothing.
- [ ] 5.2 Change the `pyproject.toml` description to "fourteen hooks", run `uv lock`, and extend `tests/test_architecture.py` to fail when the description's hook count disagrees with `len(ALL_HOOKS)`. Verify by setting it back to "eighteen" once and watching the test fail, then restoring it.

## 6. Simplification (no behaviour change)

- [ ] 6.1 Add `src/chatinho/connectors/memory.py` with `earlier()` and `speaker()` (design Decision 7), and use it from `OpenAIConnector._messages_for` and `AgentConnector._history`, removing both `_turn` functions and one `MEMORY` (the agent imports it). Verify that `tests/test_openai_connector.py` and `tests/test_agent_connector.py` pass unchanged, and that `test_architecture.py` still finds no third-party imports in the core.
- [ ] 6.2 Drop `HookSay` and `say` from `HelpCommand`. Verify `/help` tests pass, and that `hooks_of(HelpCommand)` no longer contains `HookSay`.
- [ ] 6.3 Make `composer.py` import `COMMAND_PREFIX` from `chatinho.session`, and replace `ChatFrontend._app_thread_id`/`threading` with a `_mounted` bool. Verify the threading test (`test_a_message_from_another_thread_reaches_the_log`) and the checks pass.
- [ ] 6.4 Use `preview_of` for the reply quote. Verify with a test that a short original is quoted without "…" and a long one with it.
- [ ] 6.5 Read `context()` once per `ChatLog.sync()` into an id → message dict, shared with `_render_message`. Verify the rendering tests pass.
- [ ] 6.6 Measure bubble widths with `rich.cells.cell_len`. Verify with a test that `ChatLog._bubble_width("你好")` is two cells wider than `_bubble_width("ab")`.
- [ ] 6.7 Name the parameter in `_validate_key` errors. Verify with a test that `ChatFrontend(copy_key="ctrl+h")` raises a message containing `copy_key` and not `quit_key`.

## 7. Each builder needs only its own extra

- [ ] 7.1 Move `build_chat_session` into `chatinho.frontends.chat` and `build_mcp_session` into `chatinho.frontends.mcp`. Turn `chatinho/builder.py` into a module `__getattr__` that delegates to `chatinho.__getattr__`, with `TYPE_CHECKING` imports. Point the root's lazy table at each frontend's module with one extra each (design Decision 6). Verify with `python -c "import chatinho.builder"` succeeding in a subprocess with `textual` and `fastmcp` blocked.
- [ ] 7.2 Replace `test_either_builder_needs_both_extras` in `tests/test_package_layout.py` with the spec's scenarios: each builder works without the other extra, and names its own extra when its library is missing. Verify that `test_architecture.py`'s `TYPE_CHECKING` check still passes.
- [ ] 7.3 Update CLAUDE.md (the packaging table, "builder.py imports both frontends", Layout) and README.md's install notes. Verify with `grep -rn "tui,mcp" CLAUDE.md README.md src` showing only intended mentions.

## 8. Workflow

- [ ] 8.1 Add a `python-version: ["3.12", "3.13"]` matrix to the `test` job in `.github/workflows/tests.yml`. Verify the workflow YAML parses (`python -c "import yaml; yaml.safe_load(open('.github/workflows/tests.yml'))"`, or by eye if PyYAML is absent) and that the existing steps use `${{ matrix.python-version }}`.
- [ ] 8.2 Fill `openspec/config.yaml` `context:` with the project conventions (design Decision 9). Verify with `openspec validate --all --strict --no-interactive`.
- [ ] 8.3 Find the pinned OpenSpec 1.13 CLI option that installs skills only (`openspec init --help`, `openspec update --help`). If one exists, regenerate and confirm `.claude/commands/opsx/` is gone and every `openspec-*` skill remains. If none exists, record that in this task's line and change nothing. Verify with `ls .claude/commands .claude/skills`.

## 9. Integration

- [ ] 9.1 Run the checks and `openspec validate --all --strict --no-interactive`. All must pass.
- [ ] 9.2 Re-run the four review reproductions (welcome/unknown command, bystander reply plus pinned id, error status through `ask`, archive status after restart). Each must now show the fixed behaviour.
