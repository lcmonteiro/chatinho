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
true. These names live behind an extra:

| you want | install | it brings |
|---|---|---|
| `ChatFrontend`, `ChatStyle` — the terminal | `chatinho[tui]` | `textual` |
| `McpFrontend`, `McpConnector` | `chatinho[mcp]` | `fastmcp` |
| `build_chat_session` | `chatinho[tui]` | `textual` |
| `build_mcp_session` | `chatinho[mcp]` | `fastmcp` |
| `OpenAIConnector` | `chatinho[openai]` | `openai` |
| `AgentConnector` — a LangChain agent | `chatinho[langchain]` | `langchain`, `langchain-openai` |
| `DatabaseBackend` | `chatinho[sql]` | `sqlalchemy` |
| all of them | `chatinho[all]` | all of the above |

They are resolved on first use, so `import chatinho` never drags in a terminal for a script that
wanted a session. A missing extra reports itself:

```
>>> chatinho.build_chat_session
ImportError: build_chat_session needs 'textual', which chatinho does not install by default.
             Install it with:  pip install 'chatinho[tui]'
```

Each builder imports its own frontend only when it is called, so it needs only that frontend's
extra: the terminal does not install the MCP server, nor the other way round. With the extra
missing, calling the builder says which one to install. Passing a frontend to
`ChatSession(frontend=...)` yourself is what the builder does, if you would rather.

The package ships `py.typed`, so a consumer's mypy sees the annotations.

**Renamed in 0.1.x, with no aliases:** `build_chat` is `build_chat_session`, `ChatApp` is
`ChatFrontend` (in `chatinho.frontends.chat`), and the `chatinho.chat_*` modules are gone: the core
is `chatinho.session`, `chatinho.message` and `chatinho.hooks`, and the terminal's parts live under
`chatinho.frontends.chat`. Logger names follow the modules.

**Removed in 0.1.x:** `A2AConnector` and the `chatinho[a2a]` extra. It did not speak the A2A
protocol and blocked the event loop; to put questions to another chatinho session, use
`McpConnector`.

**Changed in 0.1.x:** `OpenAIConnector.initialize()` no longer calls the API — a bad or missing key
shows up as an `error` reply to the first question instead of stopping the chat — and `answer()`
takes no per-call keyword arguments (`model`, `system_message`, `conversation_history`, …); set them
on the constructor.

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

Four rules hold everywhere: **you never hear yourself**; **nothing blocks** (every delivery is its
own task, so a peer can answer several questions at once and asks may recurse, up to
`max_depth`); **hearing is not synchronous**, so a listener sees a message shortly after it was
said; and **everything that crosses is in the context**. Connectors keep no state of the
conversation: they read it with `context()`, and the backend alone stores it.

[`docs/SPEC.md`](docs/SPEC.md) is the reference for all fourteen hooks — what each demands, what it
grants, an example, and what it costs. [`examples/hooks.py`](examples/hooks.py) is that document
executable.

---

## Using it

### Without a terminal

Nothing to install beyond the package. Write your own presentation and hand it over as the
session's `frontend`; it reaches the conversation through exactly the doors a connector does.

```python
import asyncio
from chatinho import ChatSession, HelpCommand, frontend, require, HookSay, HookInvoke, HookListen
from chatinho import Say, Invoke

@frontend("printer")
@require(HookSay)
@require(HookInvoke)
@require(HookListen)
class Printer:
    say : Say
    invoke : Invoke

    async def listen(self, msg):
        print("<", msg.text)

async def main():
    screen  = Printer()
    session = ChatSession(frontend=screen, commands=[HelpCommand()])
    await session.start()

    await screen.say("good morning")    # not printed: you never hear yourself
    await screen.invoke("help")         # printed: the answer comes from TOOL

    await session.close()               # waits for every delivery before cancelling anything

asyncio.run(main())
```

[`examples/hooks.py`](examples/hooks.py) is a complete chat with no terminal, one peer for each hook.

### With the terminal — `pip install 'chatinho[tui]'`

```python
from chatinho import build_chat_session, HelpCommand, TestCommand

build_chat_session(
    connectors = [],                                # peers: id, conversation
    commands   = [HelpCommand(), TestCommand()],    # not peers: they just run
    backend    = None,                              # a peer that listens
).run()
```

`build_chat_session` returns the **session**, with the terminal handed over as its `frontend` — an
ordinary peer that declares `@frontend("chat")`, which is `@connector` pinned to `LOCAL`. The
session owns the loop: `run()` starts
everything, runs every peer's `serve()`, and closes when the first of them returns — quitting the
terminal is the end of the chat. Markdown rendering,
syntax-highlighted code blocks, command autocomplete and click-to-reply come with it. The input
takes more than one line — **Enter sends; Ctrl+J, or a space typed before Enter, opens a line**
(Ctrl+Enter, Shift+Enter and Alt+Enter do too, on a terminal that reports them; those two always
work, and `build_chat_session(newline_escape=…)` changes the character or turns it off) — bubbles are
drawn as
outlines that grow with their text, and the one filled bubble is the message you selected to reply
to. The colours are Claude Code's — its warm neutrals and Claude's own orange — and `ChatStyle` is
a dataclass, so `dataclasses.replace` changes any one of them.

A line that starts with **`@name`** asks that peer: `@lab will it rain?` asks `lab` "will it
rain?", without the `@lab`, and its answer comes back as a reply. A line with no such peer is said
to everyone as typed.

`quit_key` moves the quit binding off Textual's `ctrl+q` — `build_chat_session(quit_key="ctrl+g")` — and a
key Textual could never receive is refused there and then, rather than becoming a binding that
silently never fires.

### With the batteries

```python
from chatinho import build_chat_session, OpenAIConnector, DatabaseBackend, Endpoint, HelpCommand

build_chat_session(
    connectors = [OpenAIConnector("gpt", Endpoint.load(), system="You are concise.")],
    commands   = [HelpCommand()],
    backend    = DatabaseBackend("sqlite:///chat.db"),
).run()
```

Needs `chatinho[all]`, or whichever extras those three names ask for.

`OpenAIConnector` talks to the `Endpoint` it is given — its URL, model and key, together (see
[Keys and endpoints](#keys-and-endpoints)): any OpenAI-compatible one, such as
`Endpoint(base_url="http://localhost:11434/v1", model="qwen")` for Ollama, or Azure, OpenRouter,
LM Studio; OpenAI and `gpt-4o` when it is left out — and never blocks the chat while the model thinks. It
remembers what its `memory` query selects — by default `Query(peer=SELF, errors=False).last(20)`,
what passed between it and anyone without the failed replies; `Query(errors=False)` for the whole
room, `None` for nothing — its own replies as `assistant` turns and everyone else's as `user`
turns, prefixed with the speaker's name when it is not you. A key lent on the message under `credential` (`llm` by default) wins over
its endpoint's key, which is therefore optional; a failure comes back as an `error` reply naming the
kind of failure, never the key.

### Keys and endpoints

A key or token argument takes the value itself (a string), or **where the value lives**: a key
source from `chatinho.keys`, read when it is needed and never kept in plain text. Errors name the
reference — the variable, the file, the command — never a value.

```python
from chatinho import Chain, Command, Endpoint, Env, File, Keyring, OpenAIConnector

key = Chain(Env("OPENAI_API_KEY"),                     # the first that has a key wins
            Keyring("chatinho", "openai"),             # the OS keychain: chatinho[keyring]
            File("~/.config/chatinho/openai.key"))     # must be chmod 600
gpt = OpenAIConnector("gpt", Endpoint(api_key=key, model="gpt-4o-mini"))
lab = OpenAIConnector("lab", Endpoint(api_key=Command("pass show api/openai")))   # run once, kept
```

`DotEnv(".env", "NAME")` reads one variable of a dotenv file. `Env`, `DotEnv` and `File` are read
anew each time, so a rotated key is used without a restart; `Keyring` and `Command` are read once.
The same sources work for `McpConnector(token=..., delegate={...})` and `McpFrontend(token=...)`.

An `Endpoint` is the URL, the model and the key together, usually a named profile in
`~/.config/chatinho/profiles.toml` (or `.chatinho.toml` in the project), where the key is only a
reference:

```toml
default = "nvidia"

[nvidia]
base_url = "https://integrate.api.nvidia.com/v1"
model    = "nvidia/nemotron-3-super-120b-a12b"
api_key  = "env:ORBE_OPENAI_API_KEY"     # env:, dotenv:PATH#NAME, file:, keyring:SVC/USER, cmd:, literal:

[local]
base_url = "http://localhost:11434/v1"
model    = "qwen2.5-coder"
api_key  = "literal:ollama"
```

```python
from chatinho import Endpoint

assistant = OpenAIConnector("assistant", Endpoint.load())                       # CHATINHO_PROFILE, else default
reviewer  = OpenAIConnector("reviewer", Endpoint.load("nvidia").with_model("other"))
```

`CHATINHO_MODEL` and `CHATINHO_BASE_URL` override a profile's fields; with no profile, the endpoint
comes from `OPENAI_API_KEY` and `OPENAI_BASE_URL`. `Endpoint.from_env("ORBE_OPENAI")` reads
`ORBE_OPENAI_API_KEY`, `_BASE_URL` and `_MODEL`, and `endpoint.check()` reads the key once so a
program can stop before it starts. A profiles file others can write is refused, since `cmd:` runs a
command.

### Agents — `pip install 'chatinho[langchain]'`

`AgentConnector` is a LangChain agent as a peer. It takes what `create_agent` takes and builds the
agent itself, adding **the chat as tools**: `ask_<peer>` for every other peer that answers, and
`run_<command>` for every command. Each question it is asked is one run of the agent:

```python
from chatinho import AgentConnector, Endpoint, OpenAIConnector

lead  = AgentConnector("lead", Endpoint.load(), tools=[search_docs],
                       system_prompt="Plan the work; ask coder for any code.", peers=["coder"])
coder = OpenAIConnector("coder", Endpoint.load())
```

`model` is anything `create_agent` takes (`"openai:gpt-4o"`, a chat model) or an `Endpoint`, whose
key is read only when the model is called. Its memory is the chat (`memory=`, the same `Query` as
`OpenAIConnector`), so it needs no checkpointer; given one, each question runs on its own thread.
`peers=` and `commands=` limit what becomes a tool, `ask_user=True` lets it ask you, and the agent
never gets a tool for itself. A peer it asks may ask it back; `ChatSession(max_depth=8)` bounds how
deep that goes. Its tools run on the chat's event loop, so blocking work belongs in
`asyncio.to_thread`.

Every answer goes through one graph, `extract -> agent -> verify -> load`, which
`await lead.graph()` returns for inspection. A tool makes a **file** by returning an artifact
(`response_format="content_and_artifact"`) that is an `Attachment`, or anything with `name`,
`media_type` and `data`; the files the run made are attached to the answer, which should link them
by name, `[chart](revenue.html)`. When it does not, `verify` sends the model back with a reminder,
at most `link_retries` times (default 1; 0 turns it off):

```python
@tool(response_format="content_and_artifact")
def draw(name: str, svg: str):
    """Draw an SVG picture the chat can show."""
    return "made %s" % name, Attachment(name=name, media_type="image/svg+xml", data=svg.encode())

painter = AgentConnector("painter", Endpoint.load(), tools=[draw])
```

A question gets a reply; what **you** say to everyone gets a say from the agent, replying to it.
What other peers say is only memory, so two agents never trade says.

### Across machines — `pip install 'chatinho[mcp]'`

One session can put questions to another over MCP (the modern protocol, 2026-07-28). On the machine
that answers, `build_mcp_session` puts an `McpFrontend` in the terminal's place — it is peer zero,
named `master` by default, and nobody types into it:

```python
from chatinho import build_mcp_session

build_mcp_session(connectors=[Agent()], token="s3cret", port=8000).run()
```

It is the same as `ChatSession(frontend=McpFrontend(token="s3cret", port=8000), connectors=[Agent()])`,
with `McpFrontend` from `chatinho.frontends`.

On the machine that asks, `McpConnector` is an ordinary peer with a name it chooses:

```python
from chatinho.connectors import McpConnector

lab = McpConnector(url="https://lab.example/mcp", token="s3cret", name="lab",
                   delegate={"llm": my_sub_key})
build_chat_session(connectors=[lab]).run()
```

Any MCP client can use it too — it needs no chatinho, only FastMCP:

```python
from fastmcp import Client

client = Client("https://lab.example/mcp", auth="s3cret")

async with client:
    peers  = (await client.call_tool("peers")).data          # [PeerInfo(name=..., answers=...)]
    result = await client.call_tool("ask", {"peer": "agent", "text": "will it rain?"})
    print(result.structured_content["text"])
```

- **The terminal's tools.** `McpFrontend` offers MCP clients what a person at the terminal can do:
  `ask` (one peer, by name), `peers`, `tools` (the slash commands) and `invoke` (one of them).
- **A question names its peer.** A question asked of `lab` goes to one remote peer: the
  `McpConnector(peer=...)` given, or else the remote session's only answering peer. With several and
  no `peer=`, the connector answers with an error — a peer router is the planned fix. In any
  chatinho session, a say in a room where exactly one peer answers is asked of that peer.
- **One reply, always.** Every question ends in exactly one of `answered`, `asked` (a question back)
  or `error`. There is no deadline: a client that stops waiting just ends its call.
  Attachments come back with the answer and the local backend keeps them.
- **The frontend speaks for every client.** It says each client's message in the remote session as
  its own, and sends the reply to that message back to the client that sent it — several clients at
  once, told apart by message id. No peer is added per client, so remote peers see every
  question coming from `master`.
- **Lending intelligence is lending a credential**, the way A2A delegates them, and it is opt-in:
  `McpFrontend(credentials={"llm": "API key"})` declares what its peers may use, and
  `McpConnector(delegate={"llm": key_or_function})` sends it out of band — serve the session over
  HTTPS, since the connector does not check the transport. It rides on the message said in the remote session, as `msg.credentials`, and the
  peer that answers uses it for that message alone — so one peer can work with a different key for
  each message. It is cleared once the message is answered. Without `delegate`, no key leaves the
  asking machine. Lend a sub-key with a spending limit or a short-lived token — never your main key.
- **Over Streamable HTTP only, with a bearer token** — required — and anyone holding it can ask every
  peer of the session. There is no stdio transport.

### Writing your own

A frontend, a connector, a command and a backend are all plain classes; the difference is what
they declare.

```python
@frontend("terminal")               # peer zero: the one that speaks for the person
@require(HookListen)
class Terminal:
    async def listen(self, msg) -> None:
        print(msg.text)

@connector("weather")               # a peer: it gets an id and its grants
@require(HookAnswer)
class Weather:
    async def answer(self, msg) -> Reply:
        return Reply("sunny")

@tool("upper", "Upper-case the rest of the line")   # not a peer: it just runs
@require(HookExecute)
class Upper:
    async def execute(self, args="", by=LOCAL, **kwargs) -> Reply:
        return Reply(args.upper())  # the answer, posted as TOOL, replying to the invocation

@backend("archive")                 # a peer that listens, loads and forgets
@require(HookListen)
@require(HookLoad)
@require(HookForget)
class Archive:
    ...
```

### Attachments

A message is Markdown text. Pages, images and files a peer attaches go to the backend, and the
text links to them by name:

```python
from chatinho import Attachment, Reply

chart = Attachment("revenue.html", "text/html", html.encode())
await self.say("Revenue is up — see the [chart](revenue.html)", attachments=[chart])

async def answer(self, msg) -> Reply:           # answers and commands attach by returning a Reply
    return Reply("Here: [report](report.html)", (Attachment("report.html", "text/html", page),))
```

The session hands attachments to the backend (`HookKeep`) before the text is posted, and nobody else
ever holds them. Any peer declaring `HookLocate` can ask where one is; the terminal does exactly that
when a message's relative link is clicked, and says "Not found" when there is no answer.
`DatabaseBackend` keeps them in its database and writes a file only when one is opened.

Attachments are whatever a peer produced — an agent's HTML page included. Treat them as untrusted
content: an HTML attachment runs its scripts when your browser opens it.

---

## Examples

| | |
|---|---|
| [`examples/assistant.py`](examples/assistant.py) | **start here** — a terminal assistant on any OpenAI-compatible model, remembering across runs |
| [`examples/team.py`](examples/team.py) | a coder and a reviewer in one room; `@coder` writes, `@reviewer` critiques what it wrote |
| [`examples/files.py`](examples/files.py) | `/read <path> [question]`: ask the model about a local text file |
| [`examples/agent.py`](examples/agent.py) | a LangChain agent that asks the coder through its `ask_coder` tool |
| [`examples/lab_server.py`](examples/lab_server.py) | a model served over MCP with no key of its own |
| [`examples/lab_client.py`](examples/lab_client.py) | a chat asking that lab, lending it your key |
| [`examples/lab_fastmcp_client.py`](examples/lab_fastmcp_client.py) | a plain FastMCP client asking the lab |
| [`examples/inbox.py`](examples/inbox.py) | `POST /ask` from a script blocks until you answer in the chat |
| [`examples/hooks.py`](examples/hooks.py) | one peer for each of the fourteen hooks, no terminal and no key |

The LLM demos need `OPENAI_API_KEY`; see [`examples/README.md`](examples/README.md).

---

## Developing

```bash
./setup.sh    # installs uv if missing, creates .venv, uv sync
./run.sh      # runs examples/assistant.py (needs OPENAI_API_KEY)
```

The three checks CI runs, from the repo root:

```bash
ruff check src tests examples
mypy src/chatinho examples
pytest -q
```

`tests/test_architecture.py` is enforcement rather than documentation: it fails if a UI import
creeps into the core, if `docs/SPEC.md` stops matching the hook constants, or if the package stops
importing without its extras.

[`CLAUDE.md`](CLAUDE.md) is the design record — why the library has this shape, and what it was
before.

### Changes go through OpenSpec

New behavior is planned with [OpenSpec](https://github.com/Fission-AI/OpenSpec) before it is
built: `openspec/specs/` holds what the library promises, `openspec/changes/` the changes in flight
and, under `archive/`, the ones that landed. CI's `openspec` job runs
`openspec validate --all --strict --no-interactive`.

In Claude Code, `/opsx:explore` thinks an idea through, `/opsx:propose "your idea"` writes the
proposal, specs, design and tasks, `/opsx:apply` implements them and `/opsx:archive` folds the
specs into `openspec/specs/`. All twelve workflows are installed (`.claude/skills/openspec-*`,
`.claude/commands/opsx/`); `/opsx:onboard` walks through a whole cycle. The CLI comes from
`npm install -g @fission-ai/openspec`, which `.claude/hooks/session-start.sh` runs for you.

## License

MIT — see [LICENSE](LICENSE).
