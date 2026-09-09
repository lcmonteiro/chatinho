# CLAUDE.md — chatinho

A TUI chat client library built on [Textual](https://textual.textualize.io/).
Extracted from the `lcmonteiro/mcking-codespace` monorepo (`python/chatinho`).

---

## Status: green

| check | result |
|---|---|
| `pytest -q` | **129 pass** |
| `ruff check src tests examples` | clean |
| `mypy src/chatinho` | clean |

Most of them run without mounting anything; only `test_chat_app.py` and
`test_command_suggestions.py` need a Textual app. That ratio is the point of the layout below, not an accident of it.

---

## Everyone is a peer

A chat is peers exchanging messages. Each has an integer id, and `LOCAL` — zero — is the user.
Connectors are numbered from one.

**A command is not a peer.** It has no id and no queue, nothing is addressed to it, and it hears
nothing. It runs when someone runs it, and it answers whoever did. Treating commands as peers meant
giving `answer` to things that only execute; they are separate parameters because they are separate
things:

```python
create_chat(
    connectors = [A2AConnector(url="…", api_key="…")],   # peers: id, queue, conversation
    commands   = [HelpCommand(), TestCommand()],         # not peers: they just run
    backend    = DatabaseBackend("sqlite:///chat.db"),   # a peer that listens
)
```

A peer carries an **id** *and* a **visible name**, and they are deliberately different
things: the id routes, the name is what the chat displays and what the user types after `/`. An
older design routed on the display name, so renaming a connector broke the replies already in
flight.

A message says where it came from and where it is going, and that is all the routing there is:

```
to is None    → everyone heard it          (say)
to is an id   → one peer was asked         (ask)
to is TOOL    → a command was run          (invoke)
reply_to set  → it answers that message    (answer)
```

**The presentation is peer zero.** `_Chat` declares the same hooks a connector does and is
attached at `LOCAL`. There is no privileged path: a terminal reaches the conversation through
exactly the doors a weather service does.

## Three verbs

| | | |
|---|---|---|
| you call | the other side writes | |
|---|---|---|
| `say(text, reply_to=)` | `listen(msg)` | a message for everyone but the speaker |
| `ask(to, text)` | `answer(msg)` | a message for one peer — **awaits** its reply |
| `invoke(name, args)` | `execute(args, by)` | a command run by name |

Every verb is a pair: the word you call, and the word the other side writes. No verb carries an
`on_` prefix, and no name is both — a grant arrives by `setattr` and would silently clobber a
method it shares a name with.

A reply to a `say` is another `say`. There is no fourth verb, and that is not an omission:
`ask`/`answer` are a pair because an ask is *addressed and owed* — one party, one reply, tracked
by the message it answers. A broadcast is owed to nobody.

**Answering late is not a fourth thing either.** A peer that cannot answer inline — a terminal
waiting on a person, a connector waiting on a server — returns `None` from `answer` and says the
reply when it has it, with `reply_to` set. The session matches it and resolves the ask. All three
presentations in this repository work exactly that way, which is why the grant that used to exist
for it was deleted: it was a second door onto the same room.

## Commands run; they are not spoken to

A peer that declares `HookInvoke` is granted `invoke(name, args)`, and a command declares
`HookExecute`. That is the whole of it:

```python
@tool("upper", "Upper-case the rest of the line")
@require(HookExecute)
@require(HookSay)                          # only for what differs from the answer
class UpperCommand:
    say : Say

    async def execute(self, args="", by=LOCAL, **kwargs) -> str:
        await self.say("working…")         # progress, said as TOOL
        return args.upper()                # the answer: posted as TOOL, and returned
```

**The invocation and the answer are both messages.** There is one conversation and everything is
in it: a say, an ask, the answer to it, a command being run and what it answered. What `execute`
returns is posted by the session in `TOOL`'s name, **replying to the invocation** — so the log
renders it the way it renders any reply, quoting the `/command` it answers and heading it `Tool`
rather than `Other`. A command that should be *seen* just returns; `HookSay` is for what differs
from the answer: progress while it works. Saying *and* returning the same text puts it in the log
twice, which is what `/help`, `/upper` and the demo's `/code` all used to do.

A command is still **not a peer** — no id, no queue, nothing addressed to it — so the invocation is
addressed to `TOOL`, id −1, and not said to the room. That is what keeps a connector that answers
what the user says from answering somebody else's `/help`: the invocation is not a broadcast, and
the answer comes from `TOOL` rather than from the user. Both halves matter, and the demo answered
its own `/help` before the constant existed.

One thing this costs, stated plainly: **a command can no longer answer privately.** What it
returns reaches everyone. There used to be a distinction between a command that wrote and one that
only answered its caller, and it is gone.

`execute` is told `by`, the id of the peer that ran it, so a command can answer differently
depending on who asked.

## Two ways to be told

| | | |
|---|---|---|
| `listen(msg)` | demands | **every** message that crosses, whoever said it, whoever it was for |
| `answer(msg)` | demands | someone asked *you*; return the reply, or `None` and say it later |

There is one way to hear, not two. `listen` brings the whole conversation — a say, an ask, the
answer to it, a command being run and what it answered — because there is one conversation and a
backend, an audit log and a metrics counter each want all of it.

A peer that only wants what was said to the room checks `msg.is_broadcast`, and it **must**: both
echo connectors in `examples/` do, and without it they would reply to a `/help` the user typed.
That check is the price of the second hook this used to be.

The two are not exclusive: something that listens *and* answers gets both calls for the same
message, because it declared both.

One rule holds across both: **you never hear yourself.** That is what stops a peer that listens
and speaks from answering its own words forever.

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
listens**: `HookListen` to hear the whole conversation, `HookLoad`/`load(since=, limit=)`
to give it back, `HookForget`/`forget(before=)` to drop it. All coroutines, all running their SQLAlchemy in
an executor so one slow write holds up nobody.

One cost, stated in the code as well as here: **`context()` is synchronous, so the window is
whatever `ChatSession(recall=…)` pulled back.** Asking for older than that returns nothing rather
than reaching down again. Making it reach would make it a coroutine, and the terminal renders its
log from inside a *synchronous* Textual paint.

## The ten hooks

The reference is [`docs/SPEC.md`](docs/SPEC.md) — every hook with an example, what it costs, and
the rules that hold across all of them. `examples/hooks.py` is that document executable: one peer
per hook, in a chat with no terminal. This section is the summary.

| hook | demands | grants |
|---|---|---|
| `HookSay` | — | `say` |
| `HookListen` | `listen` | — |
| `HookAsk` | — | `ask` |
| `HookAnswer` | `answer` | — |
| `HookInvoke` | — | `invoke` |
| `HookExecute` | `execute` | — |
| `HookContext` | — | `context` |
| `HookPeers` | — | `peers` |
| `HookLoad` | `load` | — |
| `HookForget` | `forget` | — |

Eleven became ten when the second way of hearing was folded into the first. `HookInvoke` and
`HookExecute` are still two hooks where a single one used to serve, badly — that is the honest
cost of a command not being a peer.

Every hook is one or the other — a demand or a grant, never both. `HookAnswer` was the single
exception until `answer` became the method a peer writes; the grant it also carried turned out to
be a second way of doing what `say(text, reply_to=)` already did, and nothing in the library ever
called it.

## Everything declares what it does

A peer or a command is a **plain class**. No base class, no `isinstance` anywhere in the library.

```python
@connector("weather")
@require(HookAnswer)
@require(HookSay)
class WeatherConnector:
    say : Say                       # annotate a grant, or a type checker cannot see it

    async def answer(self, msg) -> str:
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

`ChatSession.attach(obj)` registers a peer: an id, a queue, its grants, `initialize()`.
`ChatSession.add_command(cmd)` registers a command: a name, its grants, `initialize()` — no id and
no queue, because there is nothing to address or deliver.

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
  chat_app.py      create_chat + the private _Chat app — Textual presentation only  (348)
  chat_session.py  ChatSession: peers, commands, queues, routing, context           (430)
  chat_hooks.py    Hook, the ten constants,    @require, the grant protocols       (409)
  chat_message.py  ChatMessage (frm/to/reply_to) + MessageStore, LOCAL, TOOL
  chat_log.py      ChatLog widget: renders through the granted context reader
  chat_input.py    CommandInput + CommandSuggestions (autocomplete over the commands)
  chat_style.py    ChatStyle — dataclass CSS builder; use dataclasses.replace to tweak
  connectors/      a2a.py, openai.py — plain classes, no base
  commands/        help.py, test.py — commands: they run, they are not peers
  backends/        database.py (SQLAlchemy) — a peer that listens and loads
docs/              SPEC.md — the ten hooks, with an example and a cost for each
examples/          hooks.py (one peer per hook), demo.py (TUI), headless.py (stdin),
                   agent_inbox.py (HTTP, inbound)
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
- **any Textual subclass of ours takes a name that is a method on its Textual parent** — whether
  it assigns it, or is *granted* it;
- **`import chatinho` needs one of the batteries** — a subprocess imports it with `textual`,
  `openai`, `sqlalchemy` and `requests` all blocked, and each of the four lazy names has to report
  its own extra;
- **`docs/SPEC.md` disagrees with the hook constants** — its summary table has to name the same
  ten, with the same demanded method and the same grants, and each one has to have its own
  section. A spec nothing checks is a spec that rots, so adding a hook without documenting it
  fails the suite. Both halves were proved by breaking them.

That last one has bitten twice. `id` is a validated property on `DOMNode` and at least raised.
`_context` is `MessagePump`'s own context manager: shadowing it stopped the widget's message loop
with no error at all, and the only symptom was the suite going from six seconds to a timeout.
Setting `self.title` or `self.value` is ordinary use, so properties are not flagged — only the
silent case.

The grants half was added after a third near-miss: `_Chat` was granted `run`, which is Textual's
own `App.run()` — the documented way to start the app. mypy caught it because the class annotates
its grants; one that did not would have shipped it. The grant is called `invoke` now.

## Packaging: the core installs nothing

`dependencies = []`. `ChatSession`, the ten hooks, `HelpCommand` and `TestCommand` import nothing
but the standard library — which the fitness tests already enforced, so the packaging now says it
too. Four names live behind an extra and are resolved on first use with PEP 562 `__getattr__`:

| name | extra | brings |
|---|---|---|
| `create_chat` | `chatinho[tui]` | `textual` |
| `OpenAIConnector` | `chatinho[openai]` | `openai` |
| `A2AConnector` | `chatinho[a2a]` | `requests` |
| `DatabaseBackend` | `chatinho[sql]` | `sqlalchemy` |

`chatinho[all]` is all four; `chatinho[dev]` is those plus pytest, ruff and mypy, which is what CI
installs and what `setup.sh` syncs. A missing extra raises an `ImportError` that names it, rather
than surfacing as somebody else's `ModuleNotFoundError`.

`setup.sh` runs `uv sync --extra dev` explicitly: with no runtime dependencies left, whether a bare
`uv sync` puts the test tools in `.venv` depends on which uv you have.

**Not on PyPI** (checked: 404), and **there are no release tags**. Consumers install from git —
`pip install "chatinho @ git+https://github.com/lcmonteiro/chatinho.git"` — pinning a commit sha,
which is what the README documents because a `@v0.1.0` would not resolve. The wheel ships
`py.typed`, verified by building it and reading the archive.

## Public API

`__init__.py` exports 35 names: `create_chat`, `ChatSession`, `ChatMessage`, `ChatStyle`, `LOCAL`, `TOOL`;
the declaring machinery (`connector`, `tool`, `backend`, `require`, `hooks_of`, `options_of`,
`declares`, `name_of`, `Hook`); the ten `Hook*` constants; the grant protocols (`Say`, `Ask`,
`Invoke`, `Context`, `Peers`); and the batteries (`A2AConnector`, `OpenAIConnector`,
`DatabaseBackend`, `HelpCommand`, `TestCommand`).

There is no `Chat` or `ChatApp` export: the app class is private, so `create_chat` is the only way
to build one. For a chat without a terminal, build a `ChatSession` and attach your own
presentation — `examples/headless.py` is exactly that, in about forty lines.

`ChatSession`'s own public surface is six members: `attach`, `add_command`, `start`, `close`,
`id_of`, `forget`.
Everything about the conversation is reached by declaring a hook — which is what
[`docs/SPEC.md`](docs/SPEC.md) specifies, hook by hook.

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
