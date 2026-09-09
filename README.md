# chatinho

An extensible chat library. Everyone in a chat is a **peer**; there are **three verbs** and **ten
hooks**, and that is the whole of the API.

The core imports nothing but the standard library, so it embeds in a service, a bot or a test as
easily as it drives the terminal app that ships with it.

```python
from chatinho import ChatSession, HelpCommand, connector, require, HookListen, HookSay, Say

@connector("echo")
@require(HookListen)
@require(HookSay)
class Echo:
    say : Say

    async def listen(self, msg):
        if msg.is_broadcast and msg.is_local:
            await self.say("echo: %s" % msg.text, reply_to=msg.id)

session = ChatSession(connectors=[Echo()], commands=[HelpCommand()])
```

---

## Installing it in another project

Not on PyPI. Install from git:

```bash
pip install "chatinho @ git+https://github.com/lcmonteiro/chatinho.git"
uv add "chatinho @ git+https://github.com/lcmonteiro/chatinho.git"          # or with uv
```

Pin it, which is what you want in anything you will have to reproduce. There are no release tags
yet, so pin the commit:

```bash
pip install "chatinho @ git+https://github.com/lcmonteiro/chatinho.git@<sha>"
```

In a `pyproject.toml`:

```toml
[project]
dependencies = ["chatinho @ git+https://github.com/lcmonteiro/chatinho.git@<sha>"]
```

Working on both at once? Install it editable and your changes are live:

```bash
pip install -e /path/to/chatinho
```

### Extras: you install what you use

**The core has no dependencies at all.** `ChatSession`, the hooks, `HelpCommand` and `TestCommand`
need nothing beyond the standard library, and `tests/test_architecture.py` fails if that stops being
true. Four names live behind an extra:

| you want | install | it brings |
|---|---|---|
| `create_chat` — the terminal app | `chatinho[tui]` | `textual` |
| `OpenAIConnector` | `chatinho[openai]` | `openai` |
| `A2AConnector` | `chatinho[a2a]` | `requests` |
| `DatabaseBackend` | `chatinho[sql]` | `sqlalchemy` |
| all of them | `chatinho[all]` | all four |

They are resolved on first use, so `import chatinho` never drags in a terminal for a script that
wanted a session. A missing extra reports itself:

```
>>> chatinho.create_chat
ImportError: create_chat needs 'textual', which chatinho does not install by default.
             Install it with:  pip install 'chatinho[tui]'
```

The package ships `py.typed`, so a consumer's mypy sees the annotations.

**Requires Python ≥ 3.12.**

---

## The model

A chat is peers exchanging messages. Each peer has an integer id: `LOCAL` (zero) is the user,
connectors are numbered from one, and `TOOL` (minus one) is the name a command's messages carry —
because a command is not a peer.

Every verb is a pair: the word you call, and the word the other side writes.

| you call | the other side writes | |
|---|---|---|
| `say(text, reply_to=)` | `listen(msg)` | a message for everyone but the speaker |
| `ask(to, text)` | `answer(msg)` | one peer, and it owes a reply — **awaits** it |
| `invoke(name, args)` | `execute(args, by)` | a command run by name |

A peer is a **plain class** that declares what it does. No base class, no `isinstance` anywhere in
the library. `require` checks at class-definition time, so a method left out or misspelled is an
import error rather than a hook that silently never fires.

Four rules hold everywhere: **you never hear yourself**; **nothing blocks** (one queue and one task
per peer); **hearing is queued**, so a listener sees a message shortly after it was said; and
**everything that crosses is in the context**.

[`docs/SPEC.md`](docs/SPEC.md) is the reference for all ten hooks — what each demands, what it
grants, an example, and what it costs. [`examples/hooks.py`](examples/hooks.py) is that document
executable.

---

## Using it

### Without a terminal

Nothing to install beyond the package. Attach your own presentation at `LOCAL`; it reaches the
conversation through exactly the doors a connector does.

```python
import asyncio
from chatinho import ChatSession, LOCAL, HelpCommand, require, HookSay, HookInvoke, HookListen
from chatinho import Say, Invoke

@require(HookSay)
@require(HookInvoke)
@require(HookListen)
class Printer:
    say : Say
    invoke : Invoke

    async def listen(self, msg):
        print("<", msg.text)

async def main():
    session = ChatSession(commands=[HelpCommand()])
    screen  = Printer()
    session.attach(screen, at=LOCAL)
    await session.start()

    await screen.say("good morning")    # not printed: you never hear yourself
    await screen.invoke("help")         # printed: the answer comes from TOOL

    await session.close()               # drains every queue before cancelling anything

asyncio.run(main())
```

[`examples/headless.py`](examples/headless.py) is a complete stdin/stdout chat in about forty lines.

### With the terminal — `pip install 'chatinho[tui]'`

```python
from chatinho import create_chat, HelpCommand, TestCommand

create_chat(
    connectors = [],                                # peers: id, queue, conversation
    commands   = [HelpCommand(), TestCommand()],    # not peers: they just run
    backend    = None,                              # a peer that listens
).run()
```

`create_chat` is the only entry point: the application class itself is private. Markdown rendering,
syntax-highlighted code blocks, command autocomplete and click-to-reply come with it, and
`ChatStyle` is a dataclass — use `dataclasses.replace` to change a colour.

### With the batteries

```python
from chatinho import create_chat, A2AConnector, OpenAIConnector, DatabaseBackend, HelpCommand

create_chat(
    connectors = [
        A2AConnector(name="agent", url="https://api.example.com", api_key="***"),
        OpenAIConnector(name="gpt", api_key="***"),
    ],
    commands   = [HelpCommand()],
    backend    = DatabaseBackend("sqlite:///chat.db"),
).run()
```

Needs `chatinho[all]`, or whichever extras those three names ask for.

### Writing your own

A connector, a command and a backend are all plain classes; the difference is what they declare.

```python
@connector("weather")               # a peer: it gets an id and a queue
@require(HookAnswer)
class Weather:
    async def answer(self, msg) -> str:
        return "sunny"

@tool("upper", "Upper-case the rest of the line")   # not a peer: it just runs
@require(HookExecute)
class Upper:
    async def execute(self, args="", by=LOCAL, **kwargs) -> str:
        return args.upper()         # the answer, posted as TOOL, replying to the invocation

@backend("archive")                 # a peer that listens, loads and forgets
@require(HookListen)
@require(HookLoad)
@require(HookForget)
class Archive:
    ...
```

---

## Examples

| | |
|---|---|
| [`examples/hooks.py`](examples/hooks.py) | **start here** — one peer per hook, all ten, no terminal |
| [`examples/demo.py`](examples/demo.py) | the full TUI: Markdown, code blocks, autocomplete, replies |
| [`examples/headless.py`](examples/headless.py) | the same chat wired to stdin/stdout |
| [`examples/agent_inbox.py`](examples/agent_inbox.py) | inbound: an agent asks over HTTP, you answer |

---

## Developing

```bash
./setup.sh    # installs uv if missing, creates .venv, uv sync
./run.sh      # runs examples/demo.py
```

The three checks CI runs, from the repo root:

```bash
ruff check src tests examples
mypy src/chatinho
pytest -q
```

`tests/test_architecture.py` is enforcement rather than documentation: it fails if a UI import
creeps into the core, if `docs/SPEC.md` stops matching the hook constants, or if the package stops
importing without its extras.

[`CLAUDE.md`](CLAUDE.md) is the design record — why the library has this shape, and what it was
before.

## License

MIT — see [LICENSE](LICENSE).
