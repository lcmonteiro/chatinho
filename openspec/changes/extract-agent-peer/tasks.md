# Tasks

## 1. Split agent.py into helpers/agent/ (no renames, no behaviour change)

- [x] 1.1 Create `helpers/agent/results.py` (`text`, `files`, `attachment`, `shown`, `diffed`, `REMINDER`, `DIFF_SHOWN`), `graph.py` (`AgentInput/Output/State`, the `extract -> agent -> verify -> load` compile) and `tools.py` (tool names, `Shape`, the `ask_`/`run_`/`ws_` builders) from `connectors/agent.py`, and repoint `tests/fakes/agent.py` at the new `REMINDER`; verify `pytest -q tests/test_agent_connector.py tests/test_deep_agent_connector.py` passes
- [x] 1.2 Create `helpers/agent/factory.py` with the `AgentFactory` Protocol (`name`, `options`, `covered`, `async build(model, tools, options, peer)`) and `helpers/agent/basic.py` with `BasicAgent` (`create_agent`, options from its signature, `covered` empty); verify `mypy src/chatinho` passes
- [x] 1.3 Create `helpers/agent/peer.py` with `AgentPeer(name, model, factory, tools=(), ...)`: the `@require` stack, `answer`/`listen`/`_run`/`_failed`, `chat_model`, `Interrupted`, `graph()` awaiting `factory.build` and filtering `ws_` tools by `factory.covered`, option validation against `factory.options` naming `factory.name`, and the factory-facing `own_workspace()` (logs a missing provider once) and `others_workspaces()` (asked with `create=False`); verify `mypy src/chatinho` passes
- [x] 1.4 Create `helpers/agent/deep.py` with `DeepAgent(agent_memory=None)`: `create_deep_agent`, its options less `model/tools/memory/backend`, `covered` = ls/read/glob/grep/write/edit/delete, and `build` making the `CompositeBackend` (`/` own, `/peers/<name>/` others) and prefixing `WHERE`; verify that `from chatinho.helpers.agent.deep import WHERE, DeepAgent` imports
- [x] 1.5 Add `helpers/agent/__init__.py` exporting `AgentPeer`, `AgentFactory`, `BasicAgent`, `Interrupted`, with `DeepAgent` resolved lazily (PEP 562, typed under `TYPE_CHECKING`), and update the `helpers/__init__.py` docstring to say that `agent/` is behind `chatinho[langchain]`; verify with a subprocess test that importing `AgentPeer` and `BasicAgent` leaves `deepagents` out of `sys.modules`

## 2. Thin connectors under connectors/agents/

- [x] 2.1 Create `connectors/agents/basic.py` (`@connector("agent")`, `AgentPeer` + `BasicAgent()`) and `connectors/agents/deep.py` (`@connector("deep")`, `AgentPeer` + `DeepAgent(agent_memory)`, `workspace=True` by default, `backend` refused), plus a lazy `connectors/agents/__init__.py`. Delete `connectors/agent.py` and `connectors/deep.py`. Keep the class name `AgentConnector` for now. Verify the agent and deep-agent test files pass after only their imports change
- [x] 2.2 Point `connectors/__init__.py` and the lazy table and `TYPE_CHECKING` imports in `chatinho/__init__.py` at `.connectors.agents.basic` and `.connectors.agents.deep`, and update `test_package_layout.py` and `test_architecture.py` (block `deepagents` while importing `chatinho.connectors.agents` and `chatinho.helpers.agent`); verify `pytest -q tests/test_package_layout.py tests/test_architecture.py` passes
- [x] 2.3 Replace the `FACTORY` patches in `test_built_once` and the workspace-rebuild test with a patch of `create_agent` in `helpers/agent/basic` (the injected counting factory is in `test_agent_peer.py`), and add `tests/test_agent_peer.py` covering the `agent-peer` spec (custom factory awaited once with the `ask_` tools, never built when only created, rebuilt when a peer joins, an option the factory refuses names factory and option, `covered` operations get no `ws_` tools, `chatinho.AgentPeer` is an `AttributeError`); verify the new file passes and fails when `covered` filtering is removed
- [x] 2.4 Run `ruff check src tests examples`, `mypy src/chatinho examples` and `pytest -q`, and verify all are green before any rename

## 3. Rename AgentConnector to BasicAgentConnector

- [x] 3.1 Rename the class in `connectors/agents/basic.py`, `connectors/__init__.py`, `chatinho/__init__.py` (`__all__`, lazy table, `TYPE_CHECKING`), `helpers/memory.py` and the docstrings in `helpers/agent/`; verify `grep -rnw AgentConnector src` prints nothing
- [x] 3.2 Rename it in the tests (rename `test_agent_connector.py` to `test_basic_agent_connector.py`), and add the scenario that `chatinho.AgentConnector` raises `AttributeError`; verify `pytest -q` passes
- [x] 3.3 Rename it in `examples/agent.py`, `examples/workspaces.py`, `examples/deep_agent.py` and `examples/README.md`; verify `mypy src/chatinho examples` and `pytest -q tests/test_examples.py` pass

## 4. Documentation

- [x] 4.1 Update `CLAUDE.md`: the Layout tree (`connectors/agents/`, `helpers/agent/`), the packaging table and export list (`BasicAgentConnector`, still 82 names), the Workspaces section's `AgentConnector`/`DeepAgentConnector` paragraphs (factory object instead of `FACTORY`/`OPTIONS`/`_factory_options`), and a sentence naming `AgentPeer` as the second deliberate base class after `WorkspaceView`; verify `grep -nw AgentConnector CLAUDE.md` prints nothing
- [x] 4.2 Update `README.md` and `docs/SPEC.md` to the new name and import paths; verify `grep -rnw AgentConnector README.md docs` prints nothing and `pytest -q tests/test_architecture.py` (the SPEC.md check) passes

## 5. Integration

- [ ] 5.1 Run `ruff check src tests examples`, `mypy src/chatinho examples`, `pytest -q` and `openspec validate --all --strict --no-interactive`, and verify all four are green
- [ ] 5.2 After archive, retitle the scenario "AgentConnector is unchanged" to "BasicAgentConnector is unchanged" in `openspec/specs/deep-agent-connector/spec.md`, and verify `openspec validate --all --strict --no-interactive` still passes
