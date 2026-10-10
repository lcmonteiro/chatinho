# Design

## Context

Today every module of the package sits at its root:
- the core is `chat_session.py`, `chat_message.py` and `chat_hooks.py`;
- the terminal is `chat_app.py`, `chat_log.py`, `chat_input.py`, `chat_style.py` and `chat_clipboard.py`;
- `chat_builder.py` holds `build_chat`.

`McpFrontend` already lives in `frontends/mcp.py`. The architecture tests check two things by file path: that the core never imports Textual, and that only `chat_app.py`, `chat_log.py` and `chat_input.py` do. The package root resolves the names that need an extra lazily, through `_BEHIND_AN_EXTRA` and a PEP 562 `__getattr__`. `frontends/__init__.py` has its own lazy `_WHERE` table. See proposal.md for the motivation and specs/package-layout for the required public surface.

## Goals / Non-Goals

**Goals:**
- The new layout preserves file history: a move is a move, not a delete followed by an add.
- The lazy-extra behaviour stays: a missing extra is reported on first access to the name, and names the extra to install.
- The architecture tests keep enforcing the Dependency Rule against the new paths.

**Non-Goals:**
- No behaviour change: no new hooks or parameters, apart from `build_mcp_session`.
- No renames of the classes inside the moved modules (`ChatLog`, `CommandInput`, `CommandSuggestions`, `ChatStyle`). The one exception is `ChatApp`, which becomes `ChatFrontend`.
- Tests are not moved into a `tests/frontends/chat/` tree. They stay where they are, with updated imports.

## Decisions

### `ChatFrontend` is the package's `__init__.py`
The class lives in `frontends/chat/__init__.py`, so it imports as `chatinho.frontends.chat.ChatFrontend`, the same shape as `chatinho.frontends.mcp.McpFrontend`. Its helpers are submodules that the package imports relatively (`.messages`, `.composer`, `.style`, `.clipboard`).

Alternatives considered:
- A module `frontends/chat.py` next to a package `frontends/chat/`. Python cannot hold both under one name.
- `frontends/chat/chat.py` re-exported by an empty `__init__.py`. It works, but repeats the name.
- `chatinho/chat.py` at the root. It leaves Textual outside `frontends/`.

The cost is a large `__init__.py` of about 530 lines.

### Both builders in a root `builder.py`, importing both frontends at the top
`builder.py` imports `ChatFrontend`, `ChatStyle`, `NEWLINE_ESCAPE` and `McpFrontend` at module level, like any other module. The cost is that both builders need both extras, `chatinho[tui,mcp]`. A caller with only one extra passes that frontend to `ChatSession(frontend=...)` by hand, which is what each builder does.

Alternatives considered:
- Importing each frontend inside its builder. Each builder needed only its own extra, but the imports were hidden in function bodies and the type hints needed a `TYPE_CHECKING` block. This was rejected in review.
- A builder next to each frontend. This was not chosen: one module holds both builders.

### The lazy table names every extra a name needs
Each entry in `_BEHIND_AN_EXTRA` lists the `(extra, library)` pairs its name needs. When importing the defining module fails, `__getattr__` names all of them, for example "Install it with: pip install 'chatinho[tui,mcp]'". The table becomes:

```
build_chat_session : (".builder",              tui, mcp)
build_mcp_session  : (".builder",              tui, mcp)
ChatFrontend       : (".frontends.chat",       tui)
ChatStyle          : (".frontends.chat.style", tui)
McpFrontend        : (".frontends.mcp",        mcp)
... (connectors and backend unchanged, one pair each)
```

`ChatFrontend` also joins `frontends/__init__.py`'s `_WHERE`.

### `ChatStyle` goes behind `tui`
`chat_style.py` imports no Textual itself. But once it is `frontends/chat/style.py`, importing it runs `frontends/chat/__init__.py` first, and that file imports Textual. Keeping `ChatStyle` importable without the extra would mean keeping it outside the terminal's package. That contradicts the goal of keeping the terminal's parts together. A colour scheme is only useful with the terminal, so it moves behind `tui`. The `TYPE_CHECKING` block in `chatinho/__init__.py` imports it from its new place.

### Architecture tests by package, not by file list
- `CORE_MODULES` becomes `session.py`, `message.py` and `hooks.py`.
- The "only the presentation knows Textual" test asserts that every module importing Textual is under `frontends/chat/`, and that `frontends/chat/__init__.py` is among them. It no longer compares against a fixed list of files.
- A new check asserts that no core module imports `frontends` or `builder`. It extends the existing "the session does not depend on the app" test.

### Mechanical renames, then names
The work runs in two steps:
1. `git mv` every file, with no edits, as its own commit.
2. A second commit fixes the imports and renames `ChatApp` to `ChatFrontend` and `build_chat` to `build_chat_session`.

The second commit also covers the module paths inside strings, which show up in:
- `monkeypatch.setattr("chatinho.chat_log.…")`-style patches;
- `logging.getLogger` names;
- docstring cross-references (`:class:\`~chatinho.chat_session.ChatSession\``).

A final `grep -rnE "chat_(app|log|input|style|clipboard|session|message|hooks|builder)|build_chat\b|ChatApp"` over `src`, `tests`, `examples` and the docs must come back empty, except for the archived changes.

## Risks / Trade-offs

- [Patch strings that point at an old module path] → They fail loudly as `ModuleNotFoundError` or `AttributeError` when the test runs. The grep above catches the rest.
- [Logger names change from `chatinho.chat_session` to `chatinho.session`] → Anyone filtering logs by the old name loses them. This is accepted as part of the breaking rename, and the README says so.
- [`ChatStyle` now needs the `tui` extra] → A headless user who imported it for nothing loses that import, but nothing headless used it.
- [Both builders need both extras] → A terminal-only install cannot use `build_chat_session`. `ChatSession(frontend=ChatFrontend(...))` is one line, and the README shows it.
- [Users of `build_chat` / `chatinho.chat_*`] → There are no shims. The proposal marks the change **BREAKING**, the version is still 0.1.x, and the README states the new names.

## Migration Plan

- The change goes on a fresh branch from `main`, once the remaining `add-mcp-peers` follow-up commits are on `main`, so it does not stack on merged history.
- Rollback is reverting the change's commits. Nothing persisted depends on module names: the database backend stores messages, not class paths.
