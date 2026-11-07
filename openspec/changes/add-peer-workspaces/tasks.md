# Tasks

## 1. Operations and the Tree (core, no session yet)

- [x] 1.1 Create `src/chatinho/workspaces/` with `operations.py` holding `@operation(description, writes=False)` and `operations_of(cls)`. A non-coroutine is refused at class definition with `TypeError` naming it. Verify with `tests/test_workspace_operations.py`: operations come back in definition order, inherited ones included, with name, description, `writes` and parameters.
- [x] 1.2 Add `Tree` (`workspaces/tree.py`): `resolve(path)` refuses `..`, absolute paths and symlinks leaving the root with `ValueError`; `git(*args)` runs via `asyncio.create_subprocess_exec`; `files(path, glob)` uses `git ls-files --cached --others --exclude-standard`; byte reads and writes go through `asyncio.to_thread`. Verify with tests against a temporary git repo, covering escaping by `..` and by a symlink.
- [x] 1.3 Add `WorkspaceView` with `ls`, `read(path, offset, limit)`, `glob`, `grep`, `diff` and `log`, and `Match`. Verify one test per scenario of `specs/workspace-operations`: the read window, including a negative offset and a non-positive limit; glob at any depth, without ignored files; diff against the merge base, uncommitted changes included; log newest first.
- [x] 1.4 Implement `grep` with `re` (`MULTILINE`, plus `DOTALL` when `multiline=True`), in a thread, with `limit`, a truncation flag, a capped match text, non-UTF-8 files skipped, and `ValueError` for a bad pattern. Verify the single-line, multiline, "same pattern without multiline", ignored-file, over-the-limit and bad-pattern scenarios.
- [x] 1.5 Add `Workspace(WorkspaceView)` with `write`, `edit(path, old, new, replace_all)`, `delete` and `commit`, where the `@operation` wrapper takes the workspace's `asyncio.Lock` for writing operations. Verify the exact-edit, ambiguous-edit, nothing-to-commit and base-untouched scenarios, and a test in which two concurrent writes run in call order while two reads overlap.
- [x] 1.6 Add a fitness test to `tests/test_architecture.py` asserting that `chatinho.workspaces` imports only the standard library. Verify it fails when a third-party import is added to the package temporarily.

## 2. The GitWorktrees provider

- [x] 2.1 Add `GitWorktrees(repo, base=None, view=WorkspaceView, workspace=Workspace)` declaring `HookProvision`. It refuses a workspace class that does not subclass the view class, and a view class with a writing operation, both at construction. It refuses a path that is not a repository, or a `base` that does not exist, at `initialize()`, naming them. Verify one test per refusal.
- [x] 2.2 Implement `provision(owner, name)`: a worktree is created lazily at `.chatinho/worktrees/<name>` on `peer/<name>` from the base, which is read once at start; an existing one is reused; `.chatinho/` is added to `.git/info/exclude`. The owner gets a `Workspace` and others a `WorkspaceView`. Verify the created-on-first-use, reused-after-restart, close-keeps-the-work and repository-stays-clean scenarios (`git status --porcelain` empty and no tracked file changed).
- [x] 2.3 Add the operations to list, diff, merge and drop a workspace that `/ws` needs. A merge that conflicts is aborted with the conflicting paths named and the base unchanged. Verify with a conflicting branch in a temporary repo.

## 3. The session role and the hook pair

- [x] 3.1 Add `HookWorkspace` (grants `workspace`) and `HookProvision` (demands `provision`) to `hooks.py`. Update `docs/SPEC.md` (the summary table plus a section for each, with an example and a cost), `examples/hooks.py`, the hook count in `pyproject.toml`'s description, and CLAUDE.md's "fifteen hooks" table. Verify `pytest tests/test_architecture.py` passes, after first watching it fail with only the constants added.
- [x] 3.2 Add `workspaces=` to `ChatSession`: the provider is registered by what it declares, gets no id, appears in no roster and hears nothing, and a second `HookProvision` is refused. Verify the provider-in-no-roster and two-providers scenarios.
- [x] 3.3 Implement the `workspace(name=None)` grant: it returns the caller's own workspace, or another peer's view. Without a provider, it raises an error naming the missing provider. An unknown name raises `KeyError`. A command calling it without a name gets an error. Verify every scenario of the "one grant" requirement, plus a reviewer's view lacking `write`, `edit`, `delete` and `commit` (checked with `hasattr`, and noted for mypy in a comment).
- [x] 3.4 Pass `workspaces=` through `build_chat_session` and `build_mcp_session`. Verify in `tests/test_chat_session.py` that a built session serves a workspace.
- [x] 3.5 Verify that a workspace operation never blocks the chat: a test greps a large generated tree while another peer answers a say, and asserts the say is heard before the grep returns.

## 4. The /ws command

- [ ] 4.1 Add `WorkspaceCommand` (`commands/workspace.py`) with `/ws`, `/ws diff <name>` (the diff as an attachment), `/ws merge <name>` and `/ws drop <name>`. `merge` and `drop` are refused unless `by == LOCAL`. Unknown names and subcommands fail. Verify every scenario of the `/ws` requirement, including a model's `run_ws merge` being refused.
- [ ] 4.2 Add `/ws` to what `build_chat_session` registers when a provider is given, and to `/help`. Verify `/help` lists it in a built session with workspaces and not in one without.

## 5. Workspaces as agent tools

- [ ] 5.1 In `connectors/agent.py`, derive the `ws_<op>` tools for the connector's own workspace and the `ws_<op>_of` tools for every read operation, from `operations_of`, when the connector declares `HookWorkspace`. The derivation takes a filter of operation names to leave out, for `add-deep-agent-connector`. Verify with the scripted model in `tests/fakes/agent.py`: the tool list scenario, reading another's workspace, an added `symbols` operation, a failing operation returned as text, and no tools when the hook is not declared.
- [ ] 5.2 Return `diff` from its tool as an `Attachment`, so it becomes an attachment of the answer. Verify that a run calling `ws_diff` and linking the diff carries it as an attachment.

## 6. The deep agents backend adapter

- [ ] 6.1 Add the `deepagents` extra to `pyproject.toml` (`deepagents` in a compatible range), include it in `all` and `dev`, run `uv lock`, and verify `uv sync --locked --extra dev` succeeds and `langchain` moves to the version `deepagents` needs. Leave `setup.sh`'s Termux branch on `tui`, and verify that with the existing stub-based check.
- [ ] 6.2 Add `WorkspaceBackend` (`workspaces/deepagents.py`), a subclass of `BackendProtocol` wrapping a `Workspace` or `WorkspaceView`. It implements the async methods only, the sync ones raise `NotImplementedError`, it maps absolute paths to the root, and it turns every failure into the result's `error`. Verify one test per scenario of `specs/workspace-backend`, run against the real `deepagents` classes: rooted paths, escaping, missing file, ambiguous edit, literal grep, `max_count` truncation, writes going through the lock, a view refusing writes, a sync call raising.
- [ ] 6.3 Verify that `create_deep_agent(backend=WorkspaceBackend(ws))`, driven by a scripted chat model calling `write_file` and then `read_file`, writes into the worktree; that a `CompositeBackend` with a `/peers/reviewer/` route reads reviewer's file and refuses to write it; and that `execute` reports no shell.
- [ ] 6.4 Export `WorkspaceBackend` lazily: add it to `_BEHIND_AN_EXTRA` with `("deepagents", "deepagents")`, add a `TYPE_CHECKING` import, and add it to `__all__`. Verify the architecture tests: `import chatinho` with `deepagents` blocked works, and reading the name raises an `ImportError` that names `chatinho[deepagents]`.

## 7. Public API and documentation

- [ ] 7.1 Export `Workspace`, `WorkspaceView`, `operation`, `operations_of`, `Match`, `GitWorktrees`, `WorkspaceCommand`, `HookWorkspace` and `HookProvision` from `chatinho`. Update the exported-name count in CLAUDE.md. Verify `tests/test_package_layout.py`.
- [ ] 7.2 Update CLAUDE.md: a "Workspaces" section (the role, one writer, one per peer, operations by subclassing, why the base class here, the adapter and its async-only cost), the reworded sentence that "the backend is the only thing that touches the file system", the layout tree, and the packaging table row for `chatinho[deepagents]`. Verify by reading it against the specs.
- [ ] 7.3 Add `examples/workspaces.py`: two `AgentConnector`s, `dev` writing and committing and `reviewer` reading dev's diff, in a temporary repo. Wire it into `tests/test_examples.py` with the scripted model. Verify it runs under `pytest -q`.

## 8. Integration check

- [ ] 8.1 Run the four CI checks from the repo root: `ruff check src tests examples`, `mypy src/chatinho examples`, `pytest -q`, and `openspec validate --all --strict --no-interactive`. All must pass.
