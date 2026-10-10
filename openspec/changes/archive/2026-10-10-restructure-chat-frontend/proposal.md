# Proposal

## Why

The terminal is one frontend among others now, since `McpFrontend` can take peer zero, but the package does not show that. Its Textual code sits at the package root next to the core, and every module carries a `chat_` prefix whether it depends on the terminal or not. A chat over MCP also has no builder, while one with a terminal has `build_chat`. This change gives each frontend its own place, unprefixes the core, and builds both kinds of session the same way.

## What Changes

- **BREAKING** The core modules lose their prefix: `chat_session.py` becomes `session.py`, `chat_message.py` becomes `message.py`, and `chat_hooks.py` becomes `hooks.py`.
- **BREAKING** The terminal moves to the package `chatinho.frontends.chat`:
  - `chat_app.py` becomes `frontends/chat/__init__.py`, and `ChatApp` is renamed `ChatFrontend`;
  - `chat_log.py` becomes `frontends/chat/messages.py`;
  - `chat_input.py` becomes `frontends/chat/composer.py`;
  - `chat_style.py` becomes `frontends/chat/style.py`;
  - `chat_clipboard.py` becomes `frontends/chat/clipboard.py`.
  - The classes inside keep their names (`ChatLog`, `CommandInput`, `CommandSuggestions`, `ChatStyle`).
- **BREAKING** `chat_builder.py` becomes `builder.py`, with two builders:
  - `build_chat_session`, which replaces `build_chat` and keeps its parameters;
  - `build_mcp_session`, which is new and builds a session with an `McpFrontend` as peer zero.
- **BREAKING** No compatibility shims: `build_chat`, `ChatApp` and the `chatinho.chat_*` modules are gone.
- `ChatFrontend` becomes public. It sits behind the `tui` extra, as `McpFrontend` sits behind `mcp`. `ChatStyle` moves behind the `tui` extra too.
- `builder.py` imports both frontends at the top, so both builders need `chatinho[tui,mcp]`. Each frontend still needs only its own extra. A missing extra is reported as soon as the name is read off the package, naming the extras to install.
- The rest of the code and the docs follow the new names. Behaviour does not change.

## Capabilities

### New Capabilities
- `package-layout`: covers:
  - the public import paths of the core and the frontends;
  - the two session builders;
  - the extras the builders and the frontends need.

### Modified Capabilities
- `answer-details`: the "terminal asks with @name" requirement names the terminal `ChatFrontend` instead of `ChatApp`.

## Impact

- **Code:** `src/chatinho/`:
  - every `chat_*.py` module is moved or renamed;
  - `__init__.py` gets a new lazy table and `__all__`;
  - `frontends/__init__.py` gets `ChatFrontend`;
  - the relative imports in `backends/`, `commands/`, `connectors/`, `frontends/mcp.py` and `helpers/` change.
- **Tests:**
  - `tests/test_architecture.py` (module paths, the "only the terminal knows Textual" rule);
  - imports and patch strings in `conftest.py`, `test_chat_app.py` (renamed `test_chat_frontend.py`), `test_clipboard.py`, `test_command_suggestions.py`, `test_message_store.py` and `test_require.py`.
- **Examples and docs:** `examples/demo.py`, `examples/headless.py`, `examples/mcp_server.py`, `examples/README.md`, `README.md`, `docs/SPEC.md` and `CLAUDE.md`.
- **Packaging:** `pyproject.toml` only where it names modules. The extras are unchanged.
- **Users:** anyone importing `build_chat` or `chatinho.chat_*` must switch to the new names.
