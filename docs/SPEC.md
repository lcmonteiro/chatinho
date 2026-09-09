# chatinho — the hook specification

Everything a peer can do, and everything it can be asked to do, is one of **ten hooks**. This
document is the reference for all ten: what each one demands, what it grants, and what actually
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
| `0` | `LOCAL` | the user — the presentation declares `@connector("chat", id=LOCAL)`, and is a peer like any other |
| `-1` | `TOOL` | not a peer: the name a command's messages carry |

Connectors are numbered from one, in the order they are attached — unless the class pins its own
with `@connector(name, id=…)`, which is for a connector that can only ever be one peer.

A message says where it came from and where it is going, and that is the whole of the routing:

```python
ChatMessage(id, text, frm=0, to=None, reply_to=None, timestamp=...)
```

| field | when | meaning |
|---|---|---|
| `to is None` | `say` | everyone but the speaker heard it (`msg.is_broadcast`) |
| `to` is an id | `ask` | one peer was asked, and owes a reply |
| `to is TOOL` | `invoke` | a command was run |
| `reply_to` set | `answer` | it answers that message, by id |

`msg.is_local` is `frm == LOCAL`: the user said it. `msg.is_broadcast` is `to is None`.

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
2. **Nothing blocks.** Every peer has its own queue and its own task. A subsystem that takes a
   second to answer holds up nobody but itself.
3. **Hearing is queued, so it is not synchronous.** A listener sees a message shortly *after* it
   was said, not during. Assert after `close()`, which drains every queue before cancelling
   anything; asserting straight after `say()` is asserting on timing.
4. **Everything that crosses is in the context.** A say, an ask, the answer to it, a command being
   run and what it answered — one conversation, and `context()` is the window onto it.

---

## 2. The ten hooks at a glance

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
| [`HookLoad`](#hookload) | `load` | — | a backend |
| [`HookForget`](#hookforget) | `forget` | — | a backend |

**Every hook is one or the other**, never both.

Declaration is one hook per `require`, stacked, so each line can carry options that belong to that
hook alone:

```python
@connector("weather")
@require(HookAnswer)
@require(HookAsk, timeout=30)      # read back with options_of(obj, HookAsk)
class WeatherConnector:
    ask : Ask                      # annotate every grant, or mypy cannot see it

    async def answer(self, msg) -> str:
        return "sunny"
```

`require` validates **at class-definition time**: a demanded method left out or misspelled is an
import error, not a hook that silently never fires. Passing two hooks to one `require` is an error
that says to stack them instead.

---

## 3. The grants — what a peer may do

A class that declares only grants is asked for nothing.

### HookSay

> **grants** `say(text: str, *, reply_to: Optional[str] = None) -> str`

Says *text* to everyone but the speaker. Returns the new message's id.

```python
await self.say("good morning")
await self.say("echo: good morning", reply_to=msg.id)   # a reply to a say is another say
```

`reply_to` does two things at once, and the second is easy to miss: it marks the reply in the log,
**and** it is how an ask is answered late. A peer that returned `None` from `answer` resolves the
waiting ask by saying the reply with `reply_to` set to the question's id.

### HookAsk

> **grants** `await ask(to: int, text: str) -> str`

Asks the peer with id *to*, and **awaits its reply**. Raises `ValueError` if no peer has that id.

```python
answer = await self.ask(session.id_of("weather"), "what is the weather?")
```

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

> **grants** `context(*, since=None, start=None, limit=None) -> List[ChatMessage]`

The conversation so far, by time (`since`) or by index (`start`), at most `limit` of it.

```python
for msg in self.context(limit=50):
    ...
```

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

---

## 4. The demands — what a peer must write

### HookListen

> **demands** `async listen(msg: ChatMessage) -> None`

**Every** message that crosses the session, whoever said it and whoever it was for.

There is one way to hear, not two. A peer that only wants what was said to the room checks
`msg.is_broadcast` itself — and it **must**:

```python
@connector("echo")
@require(HookListen)
@require(HookSay)
class EchoConnector:
    say : Say

    async def listen(self, msg: ChatMessage) -> None:
        if not msg.is_broadcast or not msg.is_local:
            return                      # an ask, a command, or TOOL — not for it
        await self.say("echo: %s" % msg.text, reply_to=msg.id)
```

Without that guard it would reply to a `/upper` the user typed, because the invocation is a message
and it *is* local. What one listener sees, from `examples/hooks.py`:

```
   HookListen   heard from=0 to=None 'good morning'          ← said to the room
   HookListen   heard from=0 to=2 'what is the weather?'     ← an ask, not for it
   HookListen   heard from=2 to=0 'sunny'                    ← the answer to it
   HookListen   heard from=0 to=-1 '/upper nothing is hidden'    ← the invocation
   HookListen   heard from=-1 to=None 'NOTHING IS HIDDEN'    ← what it answered
```

Nothing is owed back. A backend, an audit log and a metrics counter each want all of it.

### HookAnswer

> **demands** `async answer(msg: ChatMessage) -> Optional[str]`

Someone asked *you*. What you return is the reply, posted by the session in your name.

```python
@connector("weather")
@require(HookAnswer)
class WeatherConnector:
    async def answer(self, msg: ChatMessage) -> Optional[str]:
        return "sunny"
```

**Returning `None` is not a failure.** The ask stays waiting, and whatever this peer says later
with `reply_to=msg.id` resolves it. That is how a terminal waiting on a person and a connector
waiting on a server both work — all three presentations in this repository do exactly that. There
is no separate grant for answering late: `say(text, reply_to=)` is the same door.

A peer that is asked but declares no `HookAnswer` is logged, not crashed.

### HookExecute

> **demands** `async execute(args: str = "", by: int = LOCAL, **kwargs) -> Optional[str]`

This is what a command **is**. `by` is the id of the peer that ran it, so a command may answer
differently depending on who asked.

```python
@tool("upper", "Upper-case the rest of the line")
@require(HookExecute)
class UpperCommand:
    async def execute(self, args="", by=LOCAL, **kwargs) -> str:
        return args.upper()            # the answer: posted as TOOL, and returned
```

A command is **not a peer**: no id, no queue, nothing addressed to it. It is registered with
`add_command`, not `attach`, and it is a separate parameter to `create_chat` for that reason.

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
Reached from outside by `ChatSession.forget(before=None)`.

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
@require(HookSay) @require(HookAsk) @require(HookInvoke)
@require(HookContext) @require(HookPeers)
@require(HookListen) @require(HookAnswer)
class Terminal: ...

session.attach(terminal, at=LOCAL)
```

### Demands are not exclusive

Something that listens **and** answers gets both calls for the same message, because it declared
both.

---

## 6. The session's own surface

`ChatSession` exposes six members. Everything about the conversation is reached by declaring a
hook, not by calling the session.

| | |
|---|---|
| `run()` | owns the loop: `start()`, every peer's `serve()`, then `close()` |
| `attach(who, at=None) -> int` | registers a peer: an id, a queue, its grants, `initialize()` |
| `add_command(cmd) -> str` | registers a command: a name, its grants, `initialize()` |
| `await start()` | loads the older context, then starts one task per peer |
| `await close()` | drains every queue (5s, then a warning), then shuts everything down |
| `id_of(name) -> Optional[int]` | the id of the peer with that visible name |
| `await forget(before=None) -> int` | asks the backend to drop what it held |

A peer carries an **id** and a **visible name**, and they are deliberately different: the id
routes, the name is what the chat displays and what the user types after `/`. An older design
routed on the display name, so renaming a connector broke the replies already in flight.

**Lifecycle is deliberately not a hook.** `initialize()` (synchronous, at `attach`), `async
serve()` (during `run()`, and it *runs until it is finished*) and `shutdown()` (at `close`) are
called when present. A peer holding nothing needs none of them, and making it declare that it
holds nothing is ceremony.

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
- **A peer that only wants broadcasts must filter for itself.** That check is the price of the
  second listening hook that no longer exists.
- **A command cannot answer privately**, and `context()` cannot reach past the recall window.

---

## See also

| | |
|---|---|
| `examples/hooks.py` | this document, executable — one peer per hook |
| `examples/demo.py` | the full TUI, built with `create_chat` |
| `examples/headless.py` | the same chat with no terminal, in about forty lines |
| `examples/agent_inbox.py` | the inbound direction: an agent asks over HTTP, you answer |
| `CLAUDE.md` | why the design is this shape, and what it was before |
