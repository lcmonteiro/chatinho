# Tasks

## 1. The factory seam in AgentConnector

- [x] 1.1 Move the agent factory and its accepted options into class-level points of variation on `AgentConnector`: the factory (`create_agent`), the option set derived from its signature, and a coroutine method returning extra factory keyword arguments, empty by default. Verify the whole of `tests/test_agent_connector.py` still passes unchanged, and add a test that `AgentConnector("a", model, subagents=[...])` still raises `TypeError` naming `subagents`.
- [x] 1.2 Make the set of peers that have a workspace part of the shape that decides when the graph is rebuilt, but only for a connector that uses its workspace. Verify a test where a workspace created after the first question changes the shape, and `AgentConnector` without `workspace=True` never calls `workspace()`, so no worktree appears.

## 2. Dependencies

- [x] 2.1 Widen the `deepagents` extra in `pyproject.toml` to include `langchain-openai` (an `Endpoint` becomes a `ChatOpenAI` model), mirror it in `all`, run `uv lock`, and verify `uv sync --locked --extra dev` succeeds and the architecture test that matches extras to the lazy table passes.

## 3. DeepAgentConnector

- [ ] 3.1 Add `connectors/deep.py` with `DeepAgentConnector(AgentConnector)` using `create_deep_agent`. It accepts every option that factory takes, passes `agent_memory` as deep agents' `memory`, refuses `backend` with `TypeError` saying the workspace is the backend, and defaults `workspace=True`. Verify with tests on the scripted model in `tests/fakes/agent.py` for the "options reach the agent", "memory and agent_memory", "backend refused" and "unknown option" scenarios.
- [ ] 3.2 Build the backend when the graph is built: a `CompositeBackend` whose default is `WorkspaceBackend(own workspace)` and with one `/peers/<name>/` route per other peer with a workspace, each a `WorkspaceBackend` over that peer's view. Without a provider, pass no backend and log once. Verify the "working in its own workspace", "reading another peer's work", "writing another peer's work is refused", "a workspace that appears later" and "a chat without workspaces" scenarios against real repositories (the `repo` fixture).
- [ ] 3.3 Set `COVERED` to `ls`, `read`, `glob`, `grep`, `write`, `edit` and `delete`, so the deep agent's `ws_` tools are only what its file tools cannot reach. Verify the "default tools" scenario (`ws_diff`, `ws_log`, `ws_commit`, `ws_diff_of`, `ws_log_of`) and the "project operation" scenario with an added `symbols`.
- [ ] 3.4 Prepend the paragraph about `/` and `/peers/<name>/` to the system prompt when there is a provider, keeping the given `system_prompt` after it unchanged, and leave it out without one. Verify the "user's prompt is kept" scenario by reading the system message the scripted model received, and a test that it is absent without a provider.
- [ ] 3.5 Turn a run that ends interrupted (`interrupt_on`) into an `ERROR` reply saying it was interrupted, both for a question and for a say it responds to. Verify the "interrupted run" scenario with `interrupt_on={"write_file": True}`, and check that the ask does not hang.
- [ ] 3.6 Verify the chat-side behaviour is inherited: a test runs `ask_<peer>` and a user's say through `DeepAgentConnector` on the scripted model, with the same assertions as their `AgentConnector` counterparts.

## 4. Packaging and documentation

- [ ] 4.1 Export `DeepAgentConnector` lazily from `chatinho.connectors` and `chatinho`: add it to `_BEHIND_AN_EXTRA` with `("deepagents", "deepagents")`, add a `TYPE_CHECKING` import, and add it to `__all__`. Verify with the architecture tests (an `import chatinho` with `deepagents` blocked works, and the name reports `chatinho[deepagents]`) and with `tests/test_package_layout.py`.
- [ ] 4.2 Update CLAUDE.md: the workspaces section gets a paragraph on `DeepAgentConnector` (factory seam, backend composition, `memory` vs `agent_memory`, no duplicate tools), plus the layout, packaging table and export count. Add a line to `docs/SPEC.md`'s "workspace is somewhere to work" section. Verify by reading them against the spec.
- [ ] 4.3 Add `examples/deep_agent.py`: a deep agent working in its workspace with a plain `AgentConnector` reviewer. Wire it into `tests/test_examples.py` with the scripted model and the missing-key check. Verify it runs under `pytest -q`.

## 5. Integration check

- [ ] 5.1 Run the four CI checks from the repo root: `ruff check src tests examples`, `mypy src/chatinho examples`, `pytest -q`, and `openspec validate --all --strict --no-interactive`. All must pass.
