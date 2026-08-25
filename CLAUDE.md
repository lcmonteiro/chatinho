# CLAUDE.md — chatinho

A TUI chat client library built on [Textual](https://textual.textualize.io/).
Extracted from the `lcmonteiro/mcking-codespace` monorepo (`python/chatinho`).

---

## Status: green

`import chatinho` works and all three CI checks are green.

| check | result |
|---|---|
| `pytest -q` | **47 pass** |
| `ruff check src tests examples` | clean |
| `mypy src/chatinho` | clean |

Lint and types had been red since `4350ac4` in the monorepo, when the connectors/backends/commands
layer landed; `chat_app.py` was never the cause. They were cleared alongside the recovery: unused
imports, two long lines, the SQLAlchemy `declarative_base()` pattern (now `class Base(DeclarativeBase)`,
which also silences the MovedIn20Warning) and an A2A payload annotation.

### How the package was recovered

The UI half of the old `ChatApp` — `compose`, `on_mount`, `send_message`, `receive_message`,
`send_command`, `get_replies`, `send_pending_reply`, the command-suggestion system and
`_CommandInput` — was deleted by `dbcd6bc` in the monorepo and never re-added. It was recovered
from `lcmonteiro/mcking-codespace` at `7c61e3b` (the last fully green commit) and folded into the
single `_Chat` class, together with the hook/connector orchestration from `dbcd6bc`.

The three test modules and `chat_style.py` in this repo are byte-identical to `7c61e3b`'s, which
is why the recovered UI satisfies them unchanged.

---

## One hierarchy, one entry point

`chat_app.py` used to declare its own `BaseConnector`, `BaseCommand`, `BaseBackend`,
`DatabaseBackend` and `Chat`, parallel to and unrelated to the ones in `connectors/`,
`commands/`, `backends/` and `chat.py`. That trap is gone:

- `chat_app.py` imports `BaseConnector`, `BaseCommand`, `BaseBackend` and `ChatStyle` from the
  sibling packages; it no longer defines any of them.
- The duplicate sqlite `DatabaseBackend`, the `Mock*` demo components and the module's
  `__main__` block are deleted. `backends/database.py` (SQLAlchemy) is the only backend.
- `chat.py` — the non-UI `Chat` stub whose `run()` was a print plus `time.sleep(1)` — is deleted,
  along with its copy of `create_chat`.

`create_chat()` in `chat_app.py` is the single public entry point and returns `_Chat`, a private
Textual `App`. `connectors`, `commands` and `backend` are all optional. Commands typed as
`/name` are looked up in `commands`, executed with `chat_instance=self`, and their result is
displayed as an incoming message; unregistered commands fall through to the `command_handler`
callback.

Connectors opt into events with `@hook_point(...)`; `_Chat` triggers every hook centrally
(`send_message`, `receive_message`, `execute_command`, `add_connector`, `save_data`,
`load_data`), so a connector that declares no hook points simply never gets called. The payload
each hook delivers is tabulated in `hook_point`'s docstring; `on_command_executed` is called on
both the success and the failure path with the same keys (`command`, `result`, `error`).

---

## Layout

```
src/chatinho/
  __init__.py      public API
  chat_app.py      create_chat + the private _Chat app (UI, hooks, orchestration)
  chat_style.py    ChatStyle — dataclass CSS builder; use dataclasses.replace to tweak
  connectors/      base.py (ABC), a2a.py, openai.py
  commands/        base.py (ABC), help.py, test.py
  backends/        base.py (ABC), database.py (SQLAlchemy)
examples/          demo.py
tests/             test_callbacks.py, test_chat_app.py, test_command_suggestions.py, test_hooks.py
```

## Public API

`__init__.py` exports `create_chat`, `ChatMessage`, `ChatStyle`, `hook_point` and the six `HOOK_*`
constants, `BaseConnector`, `A2AConnector`, `OpenAIConnector`, `BaseBackend`, `DatabaseBackend`,
`BaseCommand`, `HelpCommand`, `TestCommand`.

There is no `Chat` or `ChatApp` export: the app class is private, so `create_chat` is the only way
to build one. Lifecycle hooks (`on_command`, `on_message_sent`, `on_message_received`) are
customised by assigning them on the returned instance, not by subclassing.

---

## Workflow

```bash
./setup.sh    # idempotent; auto-installs uv (handles Termux via pkg), creates .venv, uv sync
./run.sh      # runs examples/demo.py (calls setup.sh first if .venv is missing)
```

Both scripts resolve paths relative to their own location, so they work from any cwd.

**Requires Python >= 3.12.** Many sandboxes default `python3` to 3.11, where the install fails
with `Package 'chatinho' requires a different Python`. Use `python3.12` explicitly if so.

The three checks CI runs (`.github/workflows/tests.yml`), all from the repo root:

```bash
ruff check src tests examples
mypy src/chatinho
pytest -q
```

---

## Conventions

Inherited from the monorepo's `python/CONTEXT.md`:

- **`uv` for everything** — `uv venv`, `uv sync`, `uv add`. Never bare `pip install` or stdlib `venv`.
- `from typing import List, Optional, Dict` — **not** PEP 585/604 builtins (`list[str]`, `str | None`).
- No `from __future__ import annotations`.
- `%`-style logging args, never f-strings: `logger.warning("Skipping %r: %s", record, exc)`.
- Align `:` and `=` in blocks of related assignments, dataclass fields, and kwargs.
- Google-style docstrings (`Args`, `Returns`, `Raises`).
- Catch specific exceptions, never bare `except:`.

Chatinho's deliberate divergences, set in `pyproject.toml` — **don't "fix" these**:

- `line-length = 110` (the monorepo standard is 100).
- `select = ["E", "F"]`, `ignore = ["E203", "E221"]` — specifically so `ruff format` won't fight
  the column-aligned style the codebase uses. The comment in `pyproject.toml` says so.

Note that much of the current code violates these rules anyway (the existing logging calls use
f-strings throughout) — the conventions are the target, not a description of the code.

---

## Provenance

Extracted from `lcmonteiro/mcking-codespace` at `python/chatinho`. **The monorepo copy still
exists** and the two will drift; the monorepo also still has its own
`.github/workflows/chatinho-tests.yml`.

Three adaptations were made for the standalone layout in `48fa4c6`:

1. `pyproject.toml` — Homepage/Repository point at `lcmonteiro/chatinho`.
2. `.github/workflows/tests.yml` — root-level CI, replacing the monorepo workflow's
   `working-directory: python/chatinho` and path filters.
3. `examples/README.md` — dropped the `python/chatinho/` path reference.

`run.sh` and `setup.sh` needed no changes.
