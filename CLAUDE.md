# CLAUDE.md — chatinho

A TUI chat client library built on [Textual](https://textual.textualize.io/).
Extracted from the `lcmonteiro/mcking-codespace` monorepo (`python/chatinho`).

---

## Status: green

| check | result |
|---|---|
| `pytest -q` | **115 pass** |
| `ruff check src tests examples` | clean |
| `mypy src/chatinho` | clean |

89 of those tests run without mounting anything, in 0.79s; the 26 that mount a Textual app take
5.0s. That ratio is the point of the layout below, not an accident of it.

---

## Everyone is a peer

A chat is peers exchanging messages. Each has an integer id, and `LOCAL` — zero — is the
user. Connectors and tools are numbered from one.

A peer carries an **id** *and* a **visible name**, and they are deliberately different
things: the id routes, the name is what the chat displays and what the user types after `/`. An
older design routed on the display name, so renaming a connector broke the replies already in
flight.

A message says where it came from and where it is going, and that is all the routing there is:

```
to is None    → everyone heard it          (say)
to is an id   → one peer was asked  (ask)
reply_to set  → it answers that message    (answer)
```

**The presentation is peer zero.** `_Chat` declares the same hooks a connector does and is
attached at `LOCAL`. There is no privileged path: a terminal reaches the conversation through
exactly the doors a weather service does.

## Three verbs

| | | |
|---|---|---|
| `say(text, reply_to=)` | grants | a message for everyone but the speaker |
| `ask(to, text)` | grants | a message for one peer — **awaits** its reply |
| `answer(msg, text)` | grants | the reply an ask is waiting on |

A reply to a `say` is another `say`. There is no fourth verb, and that is not an omission:
`ask`/`answer` are a pair because an ask is *addressed and owed* — one party, one reply, tracked
by the message it answers. A broadcast is owed to nobody.

**A command is an ask to a tool.** `/help` asks the peer named "help". Its answer arrives
as an ordinary message. There is no dispatch, no command registry and no `command_handler`;
`_Chat.command(name, args)` looks the name up and asks.

## Three ways to be told

| | | |
|---|---|---|
| `on_say(msg)` | demands | someone spoke to everyone |
| `on_ask(msg)` | demands | someone asked *you*; return the answer, or `answer()` later |
| `on_listen(msg)` | demands | **every** message that crosses, whoever said it, whoever it was for |

They are not exclusive: something that listens *and* answers gets both calls for the same message,
because it declared both.

`on_listen` is what a backend, an audit log or a metrics counter wants — everything, rather than
only the broadcasts `on_say` brings or only what was addressed to it.

One rule holds across all three: **you never hear yourself.** That is what stops a listener that
speaks from answering its own words forever.

## Nothing blocks

Everything is a coroutine, and **every peer has its own queue and its own task**. A
subsystem that takes a second to answer holds up nobody but itself —
`test_a_slow_peer_holds_up_only_itself` sends two asks, one to a peer that sleeps
0.3s and one that answers instantly, and fails if together they take more than 0.45s.

Two consequences worth knowing before they surprise you:

- **Listening is queued, so it is not synchronous.** A listener sees a message shortly after it
  was said, not during. Tests assert after `close()`, not straight after `say()`, because the
  former is a guarantee and the latter is timing.
- **`close()` drains every queue before cancelling anything.** A message still in a queue is a
  message a listener has not held yet. Five seconds, then a warning: a peer that will not
  finish must not hang the shutdown.

## Context has two tiers and one interface

A peer declares `HookContext` and calls `context(since=, start=, limit=)`. It never learns
which tier a message came from — the recent turns were said this session, the older ones were
loaded at `start()`.

The backend is not a key-value store, and nothing pushes at it. **It is a peer that
listens**: `HookListen` to hear the conversation, `HookLoad`/`load(since=, limit=)` to give it
back, `HookForget`/`forget(before=)` to drop it. All coroutines, all running their SQLAlchemy in
an executor so one slow write holds up nobody.

One cost, stated in the code as well as here: **`context()` is synchronous, so the window is
whatever `ChatSession(recall=…)` pulled back.** Asking for older than that returns nothing rather
than reaching down again. Making it reach would make it a coroutine, and the terminal renders its
log from inside a *synchronous* Textual paint.

## The nine hooks

| hook | demands | grants |
|---|---|---|
| `HookSay` | — | `say` |
| `HookAsk` | — | `ask` |
| `HookOnSay` | `on_say` | — |
| `HookOnAsk` | `on_ask` | `answer` |
| `HookContext` | — | `context` |
| `HookPeers` | — | `peers` |
| `HookListen` | `on_listen` | — |
| `HookLoad` | `load` | — |
| `HookForget` | `forget` | — |

A hook can demand a method, grant an attribute, or both. `HookOnAsk` does both, and not by
accident: being askable is what makes a way to answer worth having.

## Everything declares what it does

A peer is a **plain class**. No base class, no `isinstance` anywhere in the library.

```python
@connector("weather")
@require(HookOnAsk)
@require(HookSay)
class WeatherConnector:
    say : Say                       # annotate a grant, or a type checker cannot see it

    async def on_ask(self, msg) -> str:
        return "sunny"
```

One hook per `require`, stacked. Each declaration owns its line, so it has somewhere to carry
options that belong to that hook alone — `@require(HookAsk, timeout=30)` — read back with
`options_of(obj, HookAsk)`. Passing two hooks to one `require` is an error that says to stack
instead.

`require` validates presence and callability **at class-definition time**, so a method left out or
misspelled is an import error rather than a hook that silently never fires.

`@connector(name)`, `@tool(name, description)` and `@backend(name)` only name the class; an
instance may override with `self.name`. The session assigns the id at `attach`.

`ChatSession.attach(obj)` is the whole plugin contract: give it an id and a queue, hand over its
grants, call `initialize()` if it has one.

Lifecycle is deliberately **not** a hook: `initialize()` and `shutdown()` are called when present.
A peer holding nothing needs neither, and making it declare that it holds nothing is
ceremony. `close()` shuts down everything that has one, and the app's `on_unmount` calls it, so a
connector holding a server thread does not outlive the chat.

Two costs, stated plainly:

- **Python has no `protected`.** `_say`, `_ask`, `_context` are convention, and the grants still
  reach back — `say.__self__` *is* the session. This buys one documented door and the intent
  behind it, not enforcement.
- **With no base class, peers are typed `Any`**, so mypy no longer checks their shape.
  `require` moved that check from type-check time to import time; it did not disappear, but it is
  not the same guarantee.

---

## Layout

```
src/chatinho/
  __init__.py      public API
  chat_app.py      create_chat + the private _Chat app — Textual presentation only  (338)
  chat_session.py  ChatSession: peers, queues, routing, context                     (362)
  chat_hooks.py    Hook, the nine constants, @require, the grant protocols          (371)
  chat_message.py  ChatMessage (frm/to/reply_to) + MessageStore, LOCAL
  chat_log.py      ChatLog widget: renders through the granted context reader
  chat_input.py    CommandInput + CommandSuggestions (autocomplete over the tools)
  chat_style.py    ChatStyle — dataclass CSS builder; use dataclasses.replace to tweak
  connectors/      a2a.py, openai.py — plain classes, no base
  commands/        help.py, test.py — tools, plain classes, no base
  backends/        database.py (SQLAlchemy) — a peer that listens and loads
examples/          demo.py (TUI), headless.py (stdin), agent_inbox.py (HTTP, inbound)
tests/             test_chat_app.py, test_command_suggestions.py (mounted)
                   test_chat_session.py, test_database_backend.py, test_message_store.py,
                   test_require.py, test_architecture.py, test_a2a_payload.py (no terminal)
```

The split follows one rule: **anything that does not need Textual moves out**, because that is
what makes it testable without a terminal.

## The boundaries something checks

`tests/test_architecture.py` is not documentation, it is enforcement — a boundary nothing checks
is a boundary that rots. It parses the core modules and fails if:

- `textual` appears in their imports, or `openai`, `sqlalchemy`, `requests`, `httpx`;
- anything but the presentation layer imports Textual;
- the session imports the app;
- **any Textual subclass of ours assigns a name that is a method on its Textual parent.**

That last one has bitten twice. `id` is a validated property on `DOMNode` and at least raised.
`_context` is `MessagePump`'s own context manager: shadowing it stopped the widget's message loop
with no error at all, and the only symptom was the suite going from six seconds to a timeout.
Setting `self.title` or `self.value` is ordinary use, so properties are not flagged — only the
silent case.

## Public API

`__init__.py` exports 33 names: `create_chat`, `ChatSession`, `ChatMessage`, `ChatStyle`, `LOCAL`;
the declaring machinery (`connector`, `tool`, `backend`, `require`, `hooks_of`, `options_of`,
`declares`, `name_of`, `Hook`); the nine `Hook*` constants; the grant protocols (`Say`, `Ask`,
`Answer`, `Context`, `Peers`); and the batteries (`A2AConnector`, `OpenAIConnector`,
`DatabaseBackend`, `HelpCommand`, `TestCommand`).

There is no `Chat` or `ChatApp` export: the app class is private, so `create_chat` is the only way
to build one. For a chat without a terminal, build a `ChatSession` and attach your own
presentation — `examples/headless.py` is exactly that, in about forty lines.

`ChatSession`'s own public surface is five members: `attach`, `start`, `close`, `id_of`, `forget`.
Everything about the conversation is reached by declaring a hook.

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

`pyproject.toml` sets `asyncio_mode = "auto"`: every peer is a coroutine, so every test that
drives one is too, and marking each of them would be noise.

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

The connectors still log with f-strings, inherited from the monorepo — the conventions are the
target, not a description of every line.

---

## Provenance

Extracted from `lcmonteiro/mcking-codespace` at `python/chatinho`. **The monorepo copy still
exists** and the two have diverged substantially; the monorepo also still has its own
`.github/workflows/chatinho-tests.yml`.

The UI half of the old `ChatApp` had been deleted in the monorepo by `dbcd6bc` and never re-added;
it was recovered from `7c61e3b`, the last fully green commit, and has since been rewritten twice —
once to split Textual out of the use cases, and once to replace the vocabulary with the three verbs
above. Little of the recovered code survives, but nothing was lost to get here.

Adaptations for the standalone layout, in `48fa4c6`: `pyproject.toml` URLs, a root-level CI
workflow replacing the monorepo's `working-directory` and path filters, and a path reference in
`examples/README.md`. `run.sh` and `setup.sh` needed no changes.
