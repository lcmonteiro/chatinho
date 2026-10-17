# chatinho — the hook specification

Everything a peer can do, and everything it can be asked to do, is one of **fifteen hooks**. This
document is the reference for all fifteen: what each one demands, what it grants, and what actually
arrives at its door.

Every claim here is executable. `examples/hooks.py` declares one peer per hook and runs a short
conversation past all of them; the output quoted throughout is that program's, not a sketch of it.

```bash
python examples/hooks.py
```

---

## 1. The model, in one page

A chat is **peers** exchanging **messages**. Each peer has an integer id. Two are reserved:

| id | name | who |
|---|---|---|
| `0` | `LOCAL` | the user — the presentation declares `@frontend("chat")`, and is a peer like any other |
| `-1` | `TOOL` | not a peer: the name a command's messages carry |

Connectors are numbered from one, in the order they are attached — unless the class pins its own
with `@connector(name, id=…)`, which is for a connector that can only ever be one peer.
`@frontend(name)` is that call with `id=LOCAL` already in it, since a presentation can only ever
be peer zero.

A message says where it came from and where it is going, and that is the whole of the routing:

```python
ChatMessage(id, text, frm=0, to=None, reply_to=None, timestamp=..., status=ReplyStatus.ANSWERED, credentials={})
```

`id` and `reply_to` are `MessageID`s, not strings. `str(msg.id)` is `msg-` and 16 random hex
characters, unique across sessions, and `MessageID.parse` reads it back; `msg.id.short` is the first
seven, which is what the terminal shows.

| field | when | meaning |
|---|---|---|
| `to is None` | `say`, an answer | owed by nobody: everyone but the speaker heard it, nobody answers it |
| `to` is an id | `ask`, an addressed or routed `say` | that peer answers it |
| `to is TOOL` | `invoke` | a command was run |
| `reply_to` set | `answer` | it answers that message, by id |

**`to` is the one field that says who answers.** The speaker sets it, or leaves it unset; a say
that names nobody is given one by the **router** ([`HookRoute`](#hookroute)) before anyone hears
it, so every listener, the archive and `context()` see it already addressed. With no router of
its own, a session sends a reply to the author of what it replies to, and anything else to the one
peer that answers when there is exactly one.

What a peer's `answer` returns is an **answer**, and an answer is **addressed to nobody**: every
listener hears it, and it is never put to anyone's `answer`. So is a say replying to a message that
was addressed to its speaker — a peer answering late, or the user answering a question put to them.
That is what keeps two peers that answer from trading answers back and forth, and it is why a
follow-up to an answer is not one: the answer it replies to was addressed to nobody.

`msg.is_local` is `frm == LOCAL`: the user said it.

### Three verbs, three pairs

| you call | the other side writes | |
|---|---|---|
| `say(text, reply_to=)` | `listen(msg)` | a message for everyone but the speaker |
| `ask(to, text)` | `answer(msg)` | one peer, and it owes a reply — **awaits** it |
| `invoke(name, args)` | `execute(args, by)` | a command run by name |

No verb carries an `on_` prefix, and **no name is both a grant and a demand**: a grant arrives by
`setattr` at `attach`, and would silently clobber a method of the same name.

### Four rules that hold everywhere

1. **You never hear yourself.** No peer is delivered a message it sent. That is the whole of the
   loop protection, and it is what lets a peer both listen and speak.
2. **Nothing blocks.** Every delivery of a message to a peer is its own task. A subsystem that
   takes a second to answer holds up nobody, not even its own next question, and a peer may ask
   one that is asking it; nesting stops at `max_depth` (8) with an `ERROR` reply. Connectors
   keep no state of the conversation and must tolerate being called concurrently; the backend
   alone stores it. The frontend never waits on another peer or a command. All of this runs on
   one event loop, so nothing may block it: `answer`, `listen` and `execute` hand blocking work
   to a thread with `await asyncio.to_thread(fn, ...)`, and talk to the chat only from the loop.
3. **Hearing is not synchronous.** A listener sees a message shortly *after* it was said, not
   during. Assert after `close()`, which waits for every delivery in flight before cancelling
   anything; asserting straight after `say()` is asserting on timing.
4. **Everything that crosses is in the context.** A say, an ask, the answer to it, a command being
   run and what it answered — one conversation, and `context()` is the window onto it.

---

## 2. The fifteen hooks at a glance

| hook | demands | grants | declared by |
|---|---|---|---|
| [`HookSay`](#hooksay) | — | `say` | anything that speaks |
| [`HookListen`](#hooklisten) | `listen` | — | a connector, a backend, an audit log |
| [`HookAsk`](#hookask) | — | `ask` | a presentation, a peer that consults another |
| [`HookAnswer`](#hookanswer) | `answer` | — | a connector onto a service |
| [`HookInvoke`](#hookinvoke) | — | `invoke` | a presentation, a peer that runs commands |
| [`HookExecute`](#hookexecute) | `execute` | — | a command; this is what one *is* |
| [`HookContext`](#hookcontext) | — | `context` | a log widget, a connector that needs history |
| [`HookPeers`](#hookpeers) | — | `peers` | `/help`, the autocomplete popup |
| [`HookCommands`](#hookcommands) | — | `commands` | `/help`, the autocomplete popup |
| [`HookRoute`](#hookroute) | `route` | — | a router: the rules, or a model, deciding who answers |
| [`HookLoad`](#hookload) | `load` | — | a backend |
| [`HookForget`](#hookforget) | `forget` | — | a backend |
| [`HookKeep`](#hookkeep) | `keep` | — | a backend that keeps attachments |
| [`HookLink`](#hooklink) | `link` | — | a backend that keeps attachments |
| [`HookLocate`](#hooklocate) | — | `locate` | a presentation, a peer that opens attachments |

**Every hook is one or the other**, never both.

Declaration is one hook per `require`, stacked, so each line can carry options that belong to that
hook alone:

```python
@connector("weather")
@require(HookAnswer)
@require(HookAsk, timeout=30)      # read back with options_of(obj, HookAsk)
class WeatherConnector:
    ask : Ask                      # annotate every grant, or mypy cannot see it

    async def answer(self, msg) -> Reply:
        return Reply("sunny")
```

`require` validates **at class-definition time**: a demanded method left out or misspelled is an
import error, not a hook that silently never fires. Passing two hooks to one `require` is an error
that says to stack them instead.

---

## 3. The grants — what a peer may do

A class that declares only grants is asked for nothing.

### HookSay

> **grants** `say(text: str, *, to: Optional[int] = None, reply_to: Optional[MessageID] = None, attachments: Sequence[Attachment] = (), credentials: Optional[Dict[str, Secret]] = None) -> MessageID`

Says *text* to everyone but the speaker. Returns the new message's id. *text* is Markdown;
*attachments* go to the backend under the new message's id — see [Attachments](#attachments).

```python
await self.say("good morning")
await self.say("echo: good morning", reply_to=msg.id)   # a reply to a say is another say
```

`reply_to` does two things at once, and the second is easy to miss: it marks the reply in the log,
**and** it is how an ask is answered late. A peer that returned `None` from `answer` resolves the
waiting ask by saying the reply with `reply_to` set to the question's id.

`to` addresses the message to one peer: that peer's `answer` is called, as an ask's would be, but nobody
waits on it — the answer comes back as a reply to it, and every listener still hears both. A `to`
that is not another peer in the chat raises `ValueError`.

*credentials* ride on the message — `msg.credentials`, keys by name wrapped in `Secret` — for whoever
answers it, and nothing else: a peer can work with a different key for each message. They never
enter the text, never show in a `repr`, and the archive does not keep them; the message keeps the
very mapping it was given, so whoever lent it clears it once the message is answered.

```python
async def answer(self, msg) -> Reply:
    key = msg.credentials.get("llm")              # a Secret, or None
    model = make_model(key.reveal()) if key else self.default_model
```

Whoever lends chooses where the key comes from: `McpConnector(delegate={"llm": source})` takes a
value, a function, or a key source from `chatinho.keys` (`Env`, `File`, `Keyring`, `Command`,
`Chain`, …), read for each question. A source that cannot yield its key answers that question with an
`error` reply naming the reference, and nothing is sent.

**A say that names nobody is routed.** Leave `to` unset and the router decides it, before the say
is posted: whatever it returns becomes `to`, and that peer answers. The default router keeps two
rules. **A room with one peer that answers is a conversation with it**: a say that is not a reply
goes to the one peer besides the speaker and the frontend that declares `HookAnswer`, and with two
or more such peers, or none, to nobody. **A reply goes back to whoever it replies to**: selecting
an answer in the terminal and typing is a follow-up, and the peer that answered is the one asked; a
reply to the user, to a command's output, to a peer that only listens, or to oneself goes to
nobody. An explicit `to` always wins, and a say by a command, or one that answers a question put
to its speaker, is never routed.

### HookAsk

> **grants** `await ask(to: int, text: str, *, attachments: Sequence[Attachment] = ()) -> Reply`

Asks the peer with id *to*, and **awaits its reply**. Raises `ValueError` if no peer has that id,
and whatever the peer's `answer` raised if it failed. Only a reply from *to* resolves it: anyone
else's reply to the question is heard, and the ask keeps waiting. What comes back is a `Reply`
holding the answer's text and its status — `answered`, `asked` (a question back), or `error` when
the peer could not answer, the session's own "too many nested asks" included. Anything the reply
attached went to the backend, under the reply's id, where `locate` finds it. As text, a `Reply` reads as
what it says: `str()` is the text alone when it answered, and `asked: …` or `error: …` otherwise,
which is what an agent's `ask_<peer>` tool hands its model.

```python
reply = await self.ask(session.id_of("weather"), "what is the weather?")
if reply.status == ReplyStatus.ERROR:
    text = "weather is unavailable: %s" % reply.text    # the peer's own error reply
else:
    text = reply.text
```

What the reply said about itself is on its message: `msg.status` is `answered`, `asked` (a question
back) or `error` — a `ReplyStatus`, a `str` enum, so `msg.status == "asked"` holds — from
`Reply(..., status=ReplyStatus.ASKED)`; a `Reply` is `ANSWERED` unless it says otherwise. A peer whose `answer`
fails replies with `ReplyStatus.ERROR` when nobody is awaiting it — a say addressed to it.

`ask(LOCAL, ...)` asks the user. It does not block the chat: the awaiting peer's own task is
parked, and every other peer carries on.

### HookInvoke

> **grants** `await invoke(name: str, args: str = "") -> Optional[str]`

Runs the command called *name* and returns what it answered. `None` means no command by that name.

```python
result = await self.invoke("upper", "nothing is hidden")   # → 'NOTHING IS HIDDEN'
```

Both the invocation and the answer become messages — see [`HookExecute`](#hookexecute).

### HookContext

> **grants** `context(query=None) -> List[ChatMessage]`

The conversation so far, oldest first — and, with a `Query`, only the part you need:

```python
from chatinho import Query, SELF
for msg in self.context(Query().last(50)):              # the fifty newest
    ...
self.context(Query(peer=SELF, errors=False).last(20))   # what passed between me and anyone
self.context(Query(thread=msg.id))                      # the reply chain of one message
```

A `Query` (`peer`, `thread`, `errors`, `since`, `limit`, combined with AND) is the one way to
narrow it: there are no keywords beside it, so each filter has one spelling, and `context(limit=5)`
is a `TypeError`. `SELF` is whoever asks: the grant is bound to the asking peer, the way
`say` is. A query is plain data, not a callable, so a backend can be handed the same value one day
and answer it itself.

One interface over **two tiers**: what was said this session, and what `start()` loaded back from
the backend. Whoever asks never learns which tier a message came from.

One cost, stated plainly: `context()` is **synchronous**, so the window is whatever
`ChatSession(recall=…)` pulled back. Asking for older than that returns nothing rather than
reaching down again. Making it reach would make it a coroutine, and the terminal renders its log
from inside a *synchronous* Textual paint.

### HookPeers

> **grants** `peers() -> Dict[int, Any]`

Everyone registered, by id.

```python
others = [name_of(w) for at, w in self.peers().items() if at != LOCAL]
```

`/help` lists them and the autocomplete popup matches against them; neither could be written
without a way to see past its own class.

### HookCommands

> **grants** `commands() -> Dict[str, Any]`

Every command registered, by name.

```python
lines = ["/%s - %s" % (name, cmd.description) for name, cmd in self.commands().items()]
```

`/help` lists them and the autocomplete popup matches against them — the roster's counterpart to
`HookPeers`, for commands rather than peers.

---

## 4. The demands — what a peer must write

### HookListen

> **demands** `async listen(msg: ChatMessage) -> None`

**Every** message that crosses the session, whoever said it and whoever it was for.

There is one way to hear, not two. A peer that only wants what is owed by nobody checks
`msg.to is None` itself — and it **must**. A say the router gave a peer has `to` set, so it is that
peer's to answer, and such a listener leaves it alone; a peer that both listens *and* answers needs
nothing more, since a say addressed to it fails the same check:

```python
@connector("echo")
@require(HookListen)
@require(HookSay)
class EchoConnector:
    say : Say

    async def listen(self, msg: ChatMessage) -> None:
        if msg.to is not None or not msg.is_local:
            return                      # an ask, a routed say, a command, or TOOL — not for it
        await self.say("echo: %s" % msg.text, reply_to=msg.id)
```

Without that guard it would reply to a `/upper` the user typed, because the invocation is a message
and it *is* local. What one listener sees, from `examples/hooks.py`:

```
   HookListen   heard from=0 to=None 'good morning'          ← said to the room
   HookListen   heard from=0 to=2 'what is the weather?'     ← an ask, not for it
   HookListen   heard from=2 to=None 'sunny'                 ← the answer to it, owed by nobody
   HookListen   heard from=0 to=-1 '/upper nothing is hidden'    ← the invocation
   HookListen   heard from=-1 to=None 'NOTHING IS HIDDEN'    ← what it answered
```

Nothing is owed back. A backend, an audit log and a metrics counter each want all of it.

### HookAnswer

> **demands** `async answer(msg: ChatMessage) -> Optional[Reply]`

Someone asked *you*. The `Reply` you return is posted by the session in your name, with its
attachments and its status. Anything else — a plain string included — is a failure (`TypeError`),
as it is for a command's `execute`.

```python
@connector("weather")
@require(HookAnswer)
class WeatherConnector:
    async def answer(self, msg: ChatMessage) -> Optional[Reply]:
        return Reply("sunny")
```

**Returning `None` is not a failure.** The ask stays waiting, and whatever this peer says later
with `reply_to=msg.id` resolves it. That is how a terminal waiting on a person and a connector
waiting on a server both work — all three presentations in this repository do exactly that. There
is no separate grant for answering late: `say(text, reply_to=)` is the same door.

A peer that is asked but declares no `HookAnswer` is logged, not crashed.

### HookExecute

> **demands** `async execute(args: str = "", by: int = LOCAL, **kwargs) -> Optional[Reply]`

This is what a command **is**. `by` is the id of the peer that ran it, so a command may answer
differently depending on who asked.

```python
@tool("upper", "Upper-case the rest of the line")
@require(HookExecute)
class UpperCommand:
    async def execute(self, args="", by=LOCAL, **kwargs) -> Reply:
        return Reply(args.upper())     # the answer: posted as TOOL, and its text returned
```

A command is **not a peer**: no id, nothing addressed to it. It is registered with
`add_command`, not `add_connector`, and it is a separate parameter to `build_chat_session` for that reason.

Running one is two messages:

```
   from=0   to=a command  '/upper nothing is hidden'   ← the invocation, addressed to TOOL
   from=-1  to=everyone   'NOTHING IS HIDDEN'          ← what it answered, replying to it
```

Three consequences worth knowing before they surprise you:

- **A command that should be seen just returns.** The session posts the answer, replying to the
  invocation, so the log renders it as a reply and heads it `Tool`.
- **`HookSay` on a command is for what *differs* from the answer** — progress while it works.
  Saying *and* returning the same text writes it in the log twice.
- **A command cannot answer privately.** What it returns reaches everyone.

The invocation is *addressed* to `TOOL` rather than said to the room, which is what keeps a
connector that answers the user from answering somebody else's `/help`.

### HookRoute

> **demands** `async route(msg: ChatMessage) -> Optional[int]`

Decides who answers a say whose speaker named nobody. The session calls it for a say with `to`
unset, said by a peer (not by `TOOL`), that is not an answer, and whatever it returns becomes the
say's `to` **before** anyone hears it — so every listener, the archive and `context()` see the say
already addressed. None leaves `to` unset, and then nobody answers.

```python
@connector("triage")
@require(HookRoute)
@require(HookPeers)
class Triage:
    peers : Peers

    async def route(self, msg) -> Optional[int]:
        wanted = "meteo" if "rain" in msg.text else "gpt"
        return next((at for at, who in self.peers().items() if name_of(who) == wanted), None)
```

**The router is whichever peer declares it**, however it arrived: among the connectors, through
`add_connector`, or through `ChatSession(router=…)`, which only registers it as a peer, as
`backend=` does. So a connector that converses can route as well, and a model deciding who answers
is usually already one. A second router is refused with `ValueError`.

**With none, the session routes with `SimpleRouter`**, which is not a peer — no id, not in
`peers()` — and keeps two rules: a reply goes to the author of what it replies to, and anything
else to the one peer that answers, when there is exactly one. Both exclude the speaker and the
frontend, and both answer None otherwise.

What a router returns is checked: anything but another peer that declares `HookAnswer` is ignored
with a warning, and a router that raises is logged — the say is posted either way, with `to` unset.

### HookLoad

> **demands** `async load(since=None, limit=None) -> List[ChatMessage]`

The older context, read back **once, by `start()`**, before anyone can ask for context. A chat
reopens where it left off.

```python
async def load(self, since=None, limit=None) -> List[ChatMessage]:
    return list(self.kept)
```

A backend that cannot load is not an error: it simply has nothing to give back. One that raises is
logged, and the chat starts empty rather than failing.

### HookForget

> **demands** `async forget(before=None) -> int`

Drops what was held — everything, or only what is older than *before*. Returns how many went.
Reached from outside by `ChatSession.forget(before=None)`, which drops the same messages from the
session's own conversation first — with or without a backend — so `context()` stops returning them
at once, and returns the backend's count (0 without one).

### HookKeep

> **demands** `async keep(msg_id: MessageID, attachments: Sequence[Attachment]) -> None`

Keeps what a message carries. The session calls it **before** the message is posted, so whatever the
text links to exists by the time anyone reads it; the message itself goes on as text only.

```python
async def keep(self, msg_id, attachments) -> None:
    for item in attachments:
        self.kept[(msg_id, item.name)] = item
```

With no backend declaring it, attachments are dropped. One that raises is logged, and the text is
posted anyway.

### HookLink

> **demands** `async link(msg_id: MessageID, name: str) -> Optional[str]`

A link a browser on the same machine can open, for one kept attachment — or None when nothing by that
name was kept for that message. How it is stored and what the link looks like are the backend's
business: `DatabaseBackend` writes a file on request and answers `file://…`.

```python
async def link(self, msg_id, name) -> Optional[str]:
    return self.urls.get((msg_id, name))
```

### HookLocate

> **grants** `await locate(msg_id: MessageID, name: str) -> Optional[str]`

Where an attachment can be opened. The session asks whoever declared `HookLink`; with none, or when
it fails, the answer is None. Reached from outside by `ChatSession.locate(msg_id, name)`.

```python
url = await self.locate(msg.id, "revenue.html")
```

The terminal uses it for a message's relative links: it opens what comes back, or says "Not found".

---

## 5. Composing them

### A backend is a peer that listens

Nothing pushes at it; it is not a key-value store. It hears the conversation, gives it back, and
drops it:

```python
@backend("archive")
@require(HookListen)    # to hear the conversation
@require(HookLoad)      # to give it back at start()
@require(HookForget)    # to drop it
class ListArchive:
    ...
```

`DatabaseBackend` is exactly this, with SQLAlchemy running in an executor so one slow write holds
up nobody.

### A presentation is peer zero

The terminal declares the same hooks a connector does and is attached at `LOCAL`. There is no
privileged path: it reaches the conversation through exactly the doors a weather service does.

```python
@frontend("terminal")                                   # = @connector(name, id=LOCAL)
@require(HookSay) @require(HookAsk) @require(HookInvoke)
@require(HookContext) @require(HookPeers)
@require(HookListen) @require(HookAnswer)
class Terminal: ...

ChatSession(frontend=Terminal(), connectors=[...])
```

`frontend` and `backend` are the two roles a session takes by name, and neither is a privilege:
the session still finds what it can do by what it declared. They differ in one thing only — a
backend has no id of its own, so that parameter is pure sugar, while a frontend *is* an id, so
`frontend=` pins `LOCAL` even for something that never declared `@frontend`. A chat has one of
each: a second frontend is refused like any id already taken.

### Attachments

A message is text. What a peer attaches to it — `Attachment(name, media_type, data)`: a page, an
image, a file — goes to the backend instead, and the text links to it by name:

```python
chart = Attachment("revenue.html", "text/html", html.encode())
await self.say("Revenue is up 12% — see the [chart](revenue.html)", attachments=[chart])
```

```
   say(text, attachments) -> the session keeps them first:  backend.keep(msg_id, attachments)
                          -> then posts the text, and only the text, to everyone
   locate(msg_id, name)   -> the session asks:               backend.link(msg_id, name)
                          <- a link to open, or None
```

`say` and `ask` take `attachments`; `answer` attaches by returning a `Reply`, and `execute` always
returns one. A command's invocation (`/name args`) is a command line and carries none. No listener,
no `context()` and no archive ever holds attachment content — only the backend that declared
[`HookKeep`](#hookkeep) does, and only it touches the file system. With none, attachments are
dropped and `locate` answers None.

The terminal opens a message's **relative** links this way: it asks `locate` with the message's id
and the link's target, opens what comes back, and says "Not found" when nothing does. Absolute links
open as they always did.

### Demands are not exclusive

Something that listens **and** answers gets both calls for the same message, because it declared
both.

### An agent is a peer whose tools are the chat

`AgentConnector` (`chatinho[langchain]`) declares `HookAnswer` and grants itself the rest of the
chat: `HookPeers` and `HookAsk` become one `ask_<peer>` tool per other peer that answers, and
`HookCommands` and `HookInvoke` become one `run_<command>` tool per command. `HookContext` is its
memory. It answers each question with one run of a LangChain `create_agent` agent, built from the
same parameters. A peer it asks through a tool may ask it back: the nested question is one level
deeper, and `max_depth` stops a loop.

---

## 6. The session's own surface

`ChatSession` exposes seven members. Everything about the conversation is reached by declaring a
hook, not by calling the session.

| | |
|---|---|
| `run()` | owns the loop: `start()`, every peer's `serve()`, then `close()` |
| `add_connector(connector, at=None) -> int` | registers a peer: an id, its grants |
| `add_command(cmd) -> str` | registers a command: a name, its grants |
| `await start()` | initializes every peer/command, loads the older context, then delivers what was said before it |
| `await close()` | waits for every delivery in flight (5s, then a warning and a cancel), fails asks still waiting, then shuts everything down |
| `id_of(name) -> Optional[int]` | the id of the peer with that visible name |
| `await forget(before=None) -> int` | asks the backend to drop what it held |

A peer carries an **id** and a **visible name**, and they are deliberately different: the id
routes, the name is what the chat displays and what the user types after `/`. An older design
routed on the display name, so renaming a connector broke the replies already in flight.

**Lifecycle is deliberately not a hook.** `initialize()` (at `start()`, and may be `async def` since
there is a loop to await it by then), `async serve()` (during `run()`, and it *runs until it is
finished*) and `shutdown()` (at `close`, and may be `async def` too: `close()` awaits those
together, within its timeout, and cancels one that will not finish) are called when present. A peer holding nothing needs none
of them, and making it declare that it holds nothing is ceremony.

`run()` waits for the **first** `serve()` to return and cancels the rest: quitting the terminal is
the end of the chat even when a server is still listening. A session with nothing serving runs
until it is interrupted.

---

## 7. What this design costs

Stated rather than hidden, because each one is a real trade:

- **Python has no `protected`.** `_say`, `_ask`, `_context` are convention, and the grants still
  reach back — `say.__self__` *is* the session. This buys one documented door and the intent
  behind it, not enforcement.
- **With no base class, peers are typed `Any`**, so mypy no longer checks their shape. `require`
  moved that check from type-check time to import time; it did not disappear, but it is not the
  same guarantee.
- **A peer that only wants what is owed by nobody must filter for itself** (`msg.to is None`).
  That check is the price of the second listening hook that no longer exists, and since the
  router writes `to`, such a listener stays quiet in a room with one peer that answers.
- **A router decides before the say is posted**, so a slow one delays it. The terminal sends in a
  worker so the input stays free, but the say appears only once the router has returned.
- **A command cannot answer privately**, and `context()` cannot reach past the recall window.

---

## See also

| | |
|---|---|
| `examples/hooks.py` | this document, executable — one peer per hook |
| `examples/assistant.py` | a terminal assistant, built with `build_chat_session` |
| `examples/inbox.py` | the inbound direction: a script asks over HTTP and waits for your answer |
| `examples/README.md` | every demo, and what it needs to run |
| `CLAUDE.md` | why the design is this shape, and what it was before |
