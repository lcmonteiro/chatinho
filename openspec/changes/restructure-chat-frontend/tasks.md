# Tasks

## 1. Branch and moves

- [x] 1.1 Start a fresh branch from `main` that carries the unmerged `add-mcp-peers` follow-up commits, and verify `git log main..HEAD` shows only those commits
- [x] 1.2 `git mv` the modules with no content edits:
  - `chat_session.py` to `session.py`, `chat_message.py` to `message.py`, `chat_hooks.py` to `hooks.py`;
  - `chat_builder.py` to `builder.py`;
  - `chat_app.py` to `frontends/chat/__init__.py`, `chat_log.py` to `frontends/chat/messages.py`, `chat_input.py` to `frontends/chat/composer.py`, `chat_style.py` to `frontends/chat/style.py`, `chat_clipboard.py` to `frontends/chat/clipboard.py`.

  Verify that `git status` lists them as renames, and commit the moves on their own.

## 2. Core and frontend imports

- [x] 2.1 Update the relative imports in `session.py`, `message.py` and `hooks.py`, and the docstring cross-references (`~chatinho.chat_*`) across `src/`. Verify with `python -c "import chatinho.session, chatinho.message, chatinho.hooks"`.
- [x] 2.2 Update `frontends/chat/__init__.py`:
  - rename `ChatApp` to `ChatFrontend`;
  - import `.messages`, `.composer` and `.style`, and the core through `...session` / `...message` / `...hooks`.

  Then update `messages.py`, `composer.py`, `style.py` and `clipboard.py` (`from . import clipboard`, and `...hooks` / `...message` for the core). Verify with `python -c "from chatinho.frontends.chat import ChatFrontend"`.
- [x] 2.3 Update the core imports in `frontends/mcp.py`, `connectors/{mcp,a2a,openai}.py`, `backends/`, `commands/` and `helpers/`. Add `ChatFrontend` to `frontends/__init__.py`'s `_WHERE`, and update its docstring. Verify with `python -c "import chatinho.frontends.mcp, chatinho.connectors.mcp, chatinho.backends, chatinho.commands"`.

## 3. Builders and the package root

- [x] 3.1 In `builder.py`:
  - import both frontends at the top;
  - rename `build_chat` to `build_chat_session`, building a `ChatFrontend`;
  - add `build_mcp_session(connectors, commands, backend, name="master", *, token, host, port, credentials)`, building an `McpFrontend`.

  Verify with `python -c "from chatinho.builder import build_chat_session, build_mcp_session"`.
- [x] 3.2 Rework `chatinho/__init__.py`:
  - make the `_BEHIND_AN_EXTRA` table hold `build_chat_session`, `build_mcp_session`, `ChatFrontend`, `ChatStyle` and `McpFrontend` with their extras;
  - have each table entry list every `(extra, library)` pair its name needs, and have `__getattr__` name all of them;
  - point the core imports at the new modules;
  - drop the eager `ChatStyle` import;
  - update the `TYPE_CHECKING` block, `__all__` and the docstring (extras table, examples).

  Verify that `import chatinho` leaves `textual` and `fastmcp` out of `sys.modules`.

## 4. Tests

- [x] 4.1 Update `tests/test_architecture.py`:
  - set `CORE_MODULES` to `session.py`, `message.py` and `hooks.py`;
  - require every Textual importer to be under `frontends/chat/`;
  - check that no core module imports `frontends` or `builder`;
  - point the lazy-extra tests at the new table.

  Verify that the file passes.
- [x] 4.2 Update imports, patch strings and names (`ChatApp` to `ChatFrontend`, `build_chat` to `build_chat_session`) in `conftest.py`, `test_chat_app.py`, `test_clipboard.py`, `test_command_suggestions.py`, `test_message_store.py` and `test_require.py`. Verify that each passes.
- [x] 4.3 Add tests for the `package-layout` spec:
  - the new import paths, and that the old `chatinho.chat_*` modules are gone;
  - `from chatinho import ChatFrontend`;
  - `build_chat_session` builds a session with a `ChatFrontend` at peer zero;
  - `build_mcp_session` builds one with an `McpFrontend` named `master` on the given port, and refuses an empty token;
  - a builder without either library raises `ImportError` naming `chatinho[tui,mcp]`, while each frontend needs only its own extra (simulated by blocking the import).

  Verify that they pass.

## 5. Examples and docs

- [x] 5.1 Update the examples:
  - `examples/demo.py` uses `build_chat_session`;
  - `examples/headless.py` uses the new module names in its text;
  - `examples/mcp_server.py` uses `build_mcp_session`;
  - `examples/README.md` follows.

  Verify that `tests/test_mcp_example.py` passes and `python -c "import ast; ast.parse(open('examples/demo.py').read())"` succeeds.
- [x] 5.2 Update `README.md` (repository layout, builders, extras table, a note on the breaking rename), `docs/SPEC.md`, `CLAUDE.md` and the comments in `pyproject.toml`. Verify that the grep in design.md ("Mechanical renames, then names") returns nothing outside `openspec/changes/archive/`.

## 6. Verification

- [x] 6.1 Run the full suite, `ruff check` and `openspec validate --all --strict --no-interactive`. Verify that all tests pass (384 or more), that ruff is clean and that validation passes.
