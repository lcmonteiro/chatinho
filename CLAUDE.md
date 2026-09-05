# CLAUDE.md — chatinho

A TUI chat client library built on [Textual](https://textual.textualize.io/).
Extracted from the `lcmonteiro/mcking-codespace` monorepo (`python/chatinho`).

---

## Status: green

`import chatinho` works and all three CI checks are green.

| check | result |
|---|---|
| `pytest -q` | **115 pass** |
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

## Three verbs, and everyone has an id

Everyone in a chat is a **participant** with an integer id. `LOCAL` — zero — is the user;
connectors and tools are numbered from one. A connector carries an id *and* a visible name, and
keeping them apart is what lets it be renamed without breaking replies in flight: the old code
routed on `origin`, which was the display name.

There are three verbs and nothing else:

| | | |
|---|---|---|
| `say(text, reply_to=)` | concede | a message for everyone but the speaker |
| `ask(to, text)` | concede | a message for one participant — **awaits** its reply |
| `answer(msg, text)` | concede | the reply an ask is waiting on |
| `on_say(msg)` | exige | someone spoke to everyone |
| `on_ask(msg)` | exige | someone asked *you*; return the answer, or `answer()` later |
| `context(since=, start=, limit=)` | concede | the conversation so far, at any depth |

A reply to a `say` is another `say`. There is no fourth verb, and that is not an omission:
`ask`/`answer` are a pair because an ask is *addressed and owed* — one party, one reply, tracked
by the message it answers. A broadcast is owed to nobody.

**A command is an ask to a tool.** `/help` asks the participant named "help". That deleted
`HookExecute`, `dispatch_command`, `command_handler` and the whole idea of dispatch.

**The presentation is participant zero.** `_Chat` declares the same hooks a connector does and is
attached at `LOCAL`. `send_message`, `on_receive_message`, `inbox`, `deliver`, `origin` and
`correlation_id` are all gone from the vocabulary.

Everything is a coroutine, and **every participant has its own queue and its own task**, so a
subsystem that takes a second to answer holds up nobody but itself — `test_chat_session.py` asserts
two asks of 0.3s and 0s finish in under 0.45s.

`HookRegistry` went with them: dispatch is per-participant queues now, so nothing used it.

## Context has two tiers and one interface

The backend is not a key-value store, and nothing pushes at it. **It is a participant that
listens**: it declares `HookListen` and hears every message that crosses the session, on its own
queue, the way any participant hears anything. `HookLoad`/`load(since=, limit=)` is the other half
— it gives back what it held — and `HookForget`/`forget(before=)` drops it. All coroutines, all
running their SQLAlchemy in an executor so one slow write holds up nobody.

`HookListen` is not a backend privilege. Any participant can declare it: an audit log, a metrics
counter, anything that wants everything rather than only the broadcasts `on_say` brings or only
what was addressed to it. The one rule it shares with `say`: **you never hear yourself**, which is
what stops a listener that speaks from answering its own words forever.

A participant declares `HookContext` and calls `context(...)`. It never learns which tier a
message came from — the recent turns were said this session, the older ones were recalled at
`start()`. That is the whole point of one interface.

Two costs, both deliberate and both stated in the code:

- **`context()` is synchronous, so the window is whatever `recall` pulled back.** Asking for older
  than that returns nothing rather than reaching down again. Making it reach would make it a
  coroutine, and the terminal renders the log from inside a synchronous Textual paint.
- **Listening is queued, so it is not synchronous.** A listener sees a message shortly after it
  was said, not during. `close()` drains every queue before cancelling anything, which is what
  makes "nothing said is lost" a guarantee rather than a race — and it is why the tests assert
  after `close()` rather than straight after `say()`.

`tests/test_architecture.py` also refuses any name our Textual subclasses assign that is a
*method* on the Textual parent. Setting `self.title` or `self.value` is ordinary use; shadowing
`MessagePump._context` hung the widget's message loop with no error at all, and `id` — a validated
property on `DOMNode` — at least raised.

One thing stated plainly: Python has no `protected`. The `_` is convention, and the grants still
reach back. This buys intent and a single documented door, not enforcement.

## Everything declares what it does

Connectors, commands and backends all follow one rule: a **plain class**, no base class, no
`isinstance` anywhere, declaring its capabilities with `@require`.

```python
@command("deploy", "Ship it")
@require(HookExecute)
@require(HookSay)          # grant-only: say() is received, not implemented
class DeployCommand:
    say : Say              # annotate it, or a type checker cannot see the grant

    def execute(self, **kwargs) -> None:
        self.say("shipping…")

@backend("database")
@require(HookSave)
@require(HookLoad)
@require(HookDelete)
class DatabaseBackend: ...
```

A hook can demand a method, grant an attribute, or both. `HookSay` grants only: the class receives
`say` and implements nothing, so `require` validates nothing — declaring it is what tells the chat
to hand the capability over. `HookRegistry.trigger` refuses a grant-only hook with a warning; there
is no event to dispatch.

Separate hooks per backend operation is what lets `ChatSession` check before it calls:
`save_data` raises `Backend 'read-only' does not declare HookSave` instead of an AttributeError
somewhere deeper. That is the structural version of the `delete_data` bug — a capability the
backend never had, failing silently for months.

`add_command` refuses an object that does not declare `HookExecute`: a command that cannot execute
is not a command, and registering it silently only surfaces as a missing `/name` much later.

Commands are passed as a **list**, like connectors — the name lives on the class, so a dict key
would only be a second place for it to disagree.

## Connectors, specifically

A connector is the link between the user and an agent or API. It says what it can do by declaring
hooks:

```python
@connector("agent")
@require(HookAsk)
@require(HookAnswer)
class AgentConnector:
    def ask(self, message, **kwargs): ...          # the user asks, it answers
    def answer(self, correlation_id, text): ...    # the agent asked, the user answers
```

One hook per `require`, stacked. Each declaration owns its line, so it has somewhere to carry
options that belong to that hook alone — `@require(HookAsk, timeout=30)` — read back with
`options_of(connector, HookAsk)`. Passing two hooks to one `require` is an error that says to
stack instead.

`require` validates presence and callability **at class-definition time**, so a method left out
or misspelled is an import error rather than a hook that silently never fires. `@connector(name)`
names the class; an instance may override it with `self.name` for two links of the same kind to
different agents.

A `Hook` carries the method it demands and what the chat grants back. `HookAnswer` grants `inbox`:
the session sets it at registration, the connector calls `self.inbox(text, correlation_id)` from
its own listener, and the user's reply arrives at `answer`. The connector never imports
`ChatSession`, so the dependency still points inwards. A question that arrives carries `origin` and
`correlation_id` on its `ChatMessage`, and `ChatSession._route_reply` sends the reply back — which
means the TUI's existing click-to-reply answers an agent with no UI change at all.

Direction and event participation are declared the same way because they are the same question.
An earlier design split them — `@hook_point` for events, a `BidirectionalConnector` subclass for
direction — which was two mechanisms for one thing; the subclasses are gone.

Lifecycle is deliberately **not** a hook: `initialize()` and `shutdown()` are called when present.
A connector holding nothing needs neither, and making it declare that it holds nothing is
ceremony. `ChatSession.close()` shuts down every connector, command and backend that has one, and the app's
`on_unmount` calls it, so a connector holding a server thread does not outlive the chat.
`DatabaseBackend.shutdown()` disposes of its engine — the leak flagged in review is closed.

One cost, stated plainly: with no base class, `connectors` is typed `Any`, so mypy no longer checks
connector shape. `require` moved that check from type-check time to import time; it did not
disappear, but it is not the same guarantee.

The payload each hook delivers is tabulated in `chat_hooks.py`.

---

## Layout

```
src/chatinho/
  __init__.py      public API
  chat_app.py      create_chat + the private _Chat app — Textual presentation only
  chat_session.py  ChatSession: every use case, no UI framework
  chat_message.py  ChatMessage + MessageStore (history, ids, threading) — no Textual
  chat_hooks.py    Hook, @connector, @require, HookRegistry — no Textual
  chat_log.py      ChatLog widget: renders the store, owns the reply target
  chat_input.py    CommandInput + CommandSuggestions (autocomplete popup)
  chat_style.py    ChatStyle — dataclass CSS builder; use dataclasses.replace to tweak
  connectors/      a2a.py, openai.py — plain classes, no base
  commands/        help.py, test.py — plain classes, no base
  backends/        database.py (SQLAlchemy) — plain class, no base
examples/          demo.py, headless.py, agent_inbox.py
tests/             test_chat_app.py, test_callbacks.py, test_command_suggestions.py,
                   test_hooks.py (mounted) + test_chat_session.py, test_message_store.py,
                   test_hook_registry.py, test_architecture.py, test_database_backend.py,
                   test_connector_base.py (sync)
```

`chat_app.py` was 825 lines holding seven concerns; it is 342 now. The split follows one rule:
**anything that does not need Textual moves out**, because that is what makes it testable without
a terminal. 44 of the 91 tests now run in 1.3s without mounting an app, against 6.3s for the 47
that do.

`ChatSession` holds every use case — send/receive, command dispatch, connectors, persistence — and
imports no UI framework. `_Chat` is its Textual presentation: it owns the widget tree, the reply
target (a click is a UI concept), thread marshalling and the welcome message.

**The presentation is a plugin like any other.** It declares seven hooks and `session.attach(self)`
hands the capabilities over; there is no privileged path, and the observer slots are gone. A
terminal reaches the conversation through exactly the doors a connector does. `create_chat()` still
returns the app; `ChatSession(...)` is the headless door, and commands receive the **session** as
`chat_instance`, not a Textual `App`.

`tests/test_architecture.py` enforces this: it parses the core modules and fails if `textual`,
`openai`, `sqlalchemy` or `requests` appears in their imports, or if the session ever imports its
presentation. A boundary nothing checks is a boundary that rots.

`ChatLog` and `CommandSuggestions` are widgets that own their own children, so `_msg_widgets`,
`_rendered_msg_ids` and the popup's options left the `App`. `CommandInput` talks to its sibling
popup, which removed the six `cast(_Chat, self.app)` upward reaches. `_Chat` keeps thin delegates
(`_new_id`, `_find_message`, `_reply_target`, …) so the existing tests kept passing unchanged
through the refactor.

## Public API

`__init__.py` exports `create_chat`, `ChatMessage`, `ChatStyle`, `hook_point` and the `Hook*`
constants, `BaseConnector`, `A2AConnector`, `OpenAIConnector`, `BaseBackend`, `DatabaseBackend`,
`BaseCommand`, `HelpCommand`, `TestCommand`.

There is no `Chat` or `ChatApp` export: the app class is private, so `create_chat` is the only way
to build one. The app's own callbacks (`on_command`, `on_message_sent`, `on_message_received`) are
customised by assigning them on the returned instance, not by subclassing. Note that `on_command`
is a **notice**, not a veto: the session dispatches registered commands itself, so `/name` runs
whether or not it is replaced.

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
