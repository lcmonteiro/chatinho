# CLAUDE.md — chatinho

A TUI chat client library built on [Textual](https://textual.textualize.io/).
Extracted from the `lcmonteiro/mcking-codespace` monorepo (`python/chatinho`).

---

## ⚠️ Status: the package does not import

Do not assume anything here works. `import chatinho` raises `ImportError` on `main`:

```
src/chatinho/__init__.py:52: from .chat_app import ChatApp, ChatMessage
ImportError: cannot import name 'ChatApp' from 'chatinho.chat_app'
```

Commit `dbcd6bc` ("unify Chat logic and UI into single Chat class") is `47 insertions,
462 deletions` in one file. It deleted `class ChatApp(App)` and all ~32 of its methods —
`compose`, `on_mount`, `send_message`, `receive_message`, `send_command`, `get_replies`,
`send_pending_reply`, the whole command-suggestion system, `_CommandInput` — and never
re-added them to the new `Chat`.

Three separate failures follow from that:

| what | where | effect |
|---|---|---|
| `ChatApp` no longer exists | `src/chatinho/__init__.py:52` | `import chatinho` raises; all 3 test modules fail to collect |
| `self.add_connector()` called but undefined | `src/chatinho/chat_app.py:351` | `AttributeError` on every `Chat(...)` construction |
| no `compose()` on `Chat` | `src/chatinho/chat_app.py:300` | `run()` renders a blank screen |

`Chat(App)` currently has only: `__init__`, `_trigger_hook`, `send_message_via_connector`,
`execute_command`, `save_data`, `load_data`. `ChatMessage` (`chat_app.py:500`),
`TouchScrollableContainer` and `ChatStyle` are unreachable.

### Where it broke

Measured by checking out each commit and running the suite against it:

| commit | | tests | ruff | mypy |
|---|---|---|---|---|
| `7c61e3b` | add command autocomplete | **38 pass** | **clean** | **clean** |
| `4350ac4` | feat: extensible architecture | 27 pass | 82 err | 4 err |
| `28b0a42` | merge origin/master | 38 pass | 18 err | 3 err |
| `3b7b552` | setup.sh uv sync | 38 pass | 18 err | 3 err |
| `015445d` | merge chat_app.py and chat.py | **38 fail** | 30 err | 11 err |
| `dbcd6bc` | unify Chat logic and UI | **won't import** | 33 err | 5 err |

Two distinct regressions, not one:

- **Lint and types went red at `4350ac4`**, when the connectors/backends/commands layer landed.
  CI has been failing since then, long before the refactor.
- **Tests died at `015445d`**, one commit *before* the one that gets blamed.

`7c61e3b` is the last fully green commit.

### Recovery path

Reset `chat_app.py` to `7c61e3b`, then reintegrate the connector layer deliberately — see the
duplicate-hierarchy section below for what "deliberately" has to mean. Keeping the 38 tests
green throughout is the point; the last two commits reattached the layer blind.

**Reverting `chat_app.py` alone is not sufficient** — verified. It restores the import, but all
38 tests still fail, because `015445d` had already changed the constructor contract underneath
(`ChatApp.__init__() missing 1 required positional argument: 'chat'`).

Delete this whole section once the package is green again.

---

## The duplicate-hierarchy trap

**The single most misleading thing about this codebase.** `chat_app.py` imports *nothing* from
its sibling packages — only `logging`, `threading`, `time`, `sqlite3`, `dataclasses`, `datetime`,
`typing`, and `textual`. It declares its own copies of the base classes:

| name | `chat_app.py` defines | the real package defines |
|---|---|---|
| `BaseConnector` | `:69` | `connectors/base.py:10` (an `ABC`) |
| `BaseCommand` | `:112` | `commands/base.py:10` (an `ABC`) |
| `BaseBackend` | `:118` | `backends/base.py:10` (an `ABC`) |
| `DatabaseBackend` | `:193` (sqlite3) | `backends/database.py:30` (SQLAlchemy) |
| `Chat` | `:300` (Textual `App`) | `chat.py:40` (non-UI stub) |

These are two parallel, same-named, completely unrelated hierarchies. A
`chatinho.connectors.A2AConnector` — which subclasses `connectors/base.BaseConnector` — is **not**
the `BaseConnector` that `Chat`'s annotations refer to. Reading either half in isolation will
give you the wrong model of the package.

`chat.py:40`'s `Chat` is a stub whose `run()` is a `print` plus a `time.sleep(1)` loop, and
`create_chat` (`chat.py:69`) resolves to *that* one — not the Textual app — which contradicts
the usage example in `README.md`.

Any real fix collapses this: make `chat_app.py` import the base classes from the packages
instead of redefining them, and delete the duplicate `DatabaseBackend` and the `chat.py` stub.

---

## Layout

```
src/chatinho/
  __init__.py      public API; the back-compat block at :52 is what currently raises
  chat_app.py      Textual UI + the duplicate class hierarchy (see above)
  chat.py          non-UI Chat stub + create_chat
  chat_style.py    ChatStyle — dataclass CSS builder; use dataclasses.replace to tweak
  connectors/      base.py (ABC), a2a.py, openai.py
  commands/        base.py (ABC), help.py, test.py
  backends/        base.py (ABC), database.py (SQLAlchemy)
examples/          demo.py, new_usage.py, test_local.py
tests/             test_callbacks.py, test_chat_app.py, test_command_suggestions.py
```

## Public API

`__init__.py` exports `create_chat`, `Chat`, `BaseConnector`, `A2AConnector`, `OpenAIConnector`,
`BaseBackend`, `DatabaseBackend`, `BaseCommand`, `HelpCommand`, `TestCommand` — then a
"keep backward compatibility" block adding `ChatApp`, `ChatMessage`, `ChatStyle`. That second
block is the one that raises today.

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
