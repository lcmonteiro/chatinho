# CLAUDE.md — chatinho

A TUI chat client library built on [Textual](https://textual.textualize.io/).
Extracted from the `lcmonteiro/mcking-codespace` monorepo (`python/chatinho`).

---

## Status: green

| check | result |
|---|---|
| `pytest -q` | **246 pass** |
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
build_chat(
    connectors = [A2AConnector(url="…", api_key="…")],   # peers: id, queue, conversation
    commands   = [HelpCommand(), TestCommand()],         # not peers: they just run
    backend    = DatabaseBackend("sqlite:///chat.db"),   # a peer that listens
)
```

**Four roles, four parameters, and one of them is the terminal.** `ChatSession` takes a
`frontend` beside its `backend`: the peer that speaks for the person, the peers it talks to, the
commands it runs, the thing that remembers. Every one of them is still a plain class the session
tells apart by what it declared, never by which parameter carried it.

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

**The presentation is peer zero, and says so itself.** `ChatApp` is `@frontend("chat")` — being
the person is what it *is*, not a favour whoever attaches it does — and it declares the same hooks
a connector does. There is no privileged path: a terminal reaches the conversation through exactly
the doors a weather service does, and the session numbers everything else from one. `ChatApp` no
longer attaches itself, either: it takes no session in its constructor, and
`chat_builder.build_chat` hands it over as the session's `frontend` the same way it would hand
over any other peer.

**`@frontend(name)` is `@connector(name, id=LOCAL)`, and exists because writing that out is an
invitation to get it wrong.** Three presentations in this repository wrote it by hand, and a
fourth — `examples/hooks.py` — pinned the id at the call site instead, which is a second way of
saying the same thing. Peer zero is what a presentation *is*; now it declares that, and the
`frontend=` parameter is where it goes.

The two roles differ in exactly one thing, and it is worth knowing before it surprises you: a
backend has no id of its own, so `backend=` is pure sugar for the role, while a frontend *is* an
id, so `frontend=` **pins** `LOCAL` even for something that never declared `@frontend`. Without
that, passing an ordinary connector there would land it at one and leave the chat with nobody at
zero — and nothing would say so. A second frontend is refused like any id already taken.

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

## The eleven hooks

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
| `HookCommands` | — | `commands` |
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
`@frontend(name)` is the exception that proves it: it names the class *and* pins `LOCAL`, because
that is not a choice a presentation gets to make. The name defaults to `chat`, so `@frontend()`
is enough; `@frontend` without the parentheses is refused, the class having arrived where the name
belongs.

`ChatSession.add_connector(obj)` registers a peer: an id, a queue, its grants. `ChatSession.add_command(cmd)`
registers a command: a name, its grants — no id and no queue, because there is nothing to address
or deliver. Neither calls `initialize()`; `start()` does, for both, once each has a loop to use.

Lifecycle is deliberately **not** a hook: `initialize()`, `serve()` and `shutdown()` are called
when present. A peer holding nothing needs none of them, and making it declare that it holds
nothing is ceremony.

| | when | |
|---|---|---|
| `initialize()` | at `start()` | may be `async def` — `start()` awaits it when it is, and just calls it when it isn't |
| `async serve()` | during `run()` | **runs until it is finished.** A terminal, a stdin reader, a server |
| `shutdown()` | at `close` | synchronous; a connector holding a thread must not outlive the chat |

**`ChatSession.run()` owns the loop**: `asyncio.run(...)` inside, `start()`, then every `serve()`
as its own task, and `close()` on the way out. The **first** `serve()` to return ends the chat —
quitting the terminal is the end of it even when a server is still listening — and the rest are
cancelled. A session with nothing serving runs until it is interrupted, which is what a bot wants.
Cancellation is not swallowed; `run()` turns the Ctrl-C case into a quiet exit itself.

That is the inversion: the session drives, and the terminal is a peer it serves. `ChatApp.serve()` is
`await self.run_async()` — `run()` would try to start a second loop inside the session's own.

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
  chat_app.py      ChatApp — Textual presentation only, no session of its own
  chat_builder.py  build_chat — builds a ChatSession and ChatApp, wires the two
  chat_session.py  ChatSession: run, peers, commands, queues, routing, context      (545)
  chat_hooks.py    Hook, the ten constants,    @require, the grant protocols       (489)
  chat_message.py  ChatMessage (frm/to/reply_to) + MessageStore, LOCAL, TOOL
  chat_log.py      ChatLog widget: renders through the granted context reader
  chat_input.py    CommandInput (a multi-line TextArea) + CommandSuggestions
  chat_clipboard.py  OSC 52's second route: a clipboard helper, if the system has one
  chat_style.py    ChatStyle — dataclass CSS builder; use dataclasses.replace to tweak
  connectors/      a2a.py, openai.py — plain classes, no base
  commands/        help.py, test.py — commands: they run, they are not peers
  backends/        database.py (SQLAlchemy) — a peer that listens and loads
docs/              SPEC.md — the eleven hooks, with an example and a cost for each
examples/          hooks.py (one peer per hook), demo.py (TUI), headless.py (stdin),
                   agent_inbox.py (HTTP, inbound)
tests/             test_chat_app.py, test_command_suggestions.py (mounted)
                   test_chat_session.py, test_database_backend.py, test_message_store.py,
                   test_require.py, test_architecture.py, test_a2a_payload.py,
                   test_clipboard.py (no terminal)
```

The split follows one rule: **anything that does not need Textual moves out**, because that is
what makes it testable without a terminal.

## The chat is drawn as outlines

A bubble is a **border and nothing else** — the chat background shows through it. The one filled
thing in the log is the message you have selected to reply to, which is what the two `*_bubble_bg`
fields in `ChatStyle` now mean, and the fill is the *whole* of the selection: there is no second
outline on top of it. **Which side you are on is `ChatStyle.local_align`**, and the default is
`"right"`: everyone else is always on the left, so your own messages on the other side make the
conversation read as two columns, which is what a chat looks like. `"left"` puts everyone in one.
The cost is real and was the reason it defaulted the other way — a right-hand column says what the
header and the border colour already said, and it costs half the width to say it — but a chat that
does not sort by side does not read as a chat, and the width is there on a terminal. On a phone it
is not, which is what `"left"` is for. A value that is neither side is refused at construction,
because Textual would take the broken rule and report it nowhere the caller would look.

**The chat is centred, and `chat_max_width` caps it.** A line the width of a desk is a line nobody
reads across, so a wide terminal gives margins instead. It is a *maximum* and not a width: on a
phone the body takes all sixty columns and wastes none. `#input-area` is `dock: bottom`, which is
relative to its parent — now the narrower body rather than the screen — and a test says the input
moved in with it, after first asserting the body really is narrower, or it would pass just as well
with no centring at all.

**A peer is one colour, and the header wears it above the bubble.** `ChatStyle.peer_headers` is a
palette indexed by the peer's id — slot zero is the user — and it wraps round when there are more
peers than colours. `to_css()` renders two rules per entry, plus `.peer-tool` because a command has
no id of its own: the header's `color` and the bubble's `border`. The header is a *sibling* of the
bubble rather than a child, so the bubble holds only what was said — but it still sets the bubble's
**minimum** width — the header's own indent plus one space, so the two do not end flush — because a
bubble narrower than the header sitting on it reads as two things rather than one.

**A header sized by its own text hugs the wrong edge, and `align` will not fix it.** Textual moves
the header and the bubble as one *block*; it does not align within that block, so a header left to
size itself stays against the bubble's left edge whichever side the block landed on. On the right,
under a wide bubble, that strands it up to fifty cells from the message it names — which looked
like the header not having moved at all. `ChatLog` gives the header the bubble's own measured span
less `_HEADER_SLACK` (the border cell at each end), and `.message-container.sent .message-header`
takes `text-align: $local_align`, so the text lands on the side the bubble took. A header too long
for that span keeps its own width, exactly as it did before.

**And a span in cells is not a width either — the header needed `max-width: 100%` too.** The
bubble learned that lesson; the header was handed the same measured span and nothing to clamp it
with, so below about 64 columns its box ran past the log and the right-aligned text inside it
landed off-screen: truncated at 60 (`14:25 @chat · ms`), **invisible** at 50 and 40. That is
phone width, which is the terminal this is for. The one test of the header ran at 96 columns,
where the bubble is narrower than the screen and nothing overflows, so the suite never saw it;
there is one at 40, 50 and 60 now. The clamp costs the `_HEADER_SLACK` inset at those widths —
the header ends flush with the bubble instead of a cell inside it — which is a trade against not
being there at all.

The test reads the *rendered* header line and finds where the ink is, not where the box is: now
that the box spans the bubble on both sides, a box measurement passes with the text stranded at
either end of it. Both halves were broken separately to watch it fail — the width alone leaves the
text at the far end, and the `text-align` alone has nothing to align inside. The hues
are spread apart deliberately: the common chat is the user and one connector, so slots 0 and 1 have
to be told apart at a glance, and the two greens they started as could not be.

**The input is ruled off rather than boxed in.** `input_frame` is `"lines"`: a rule above and a
rule below, and nothing at the sides. A box is a widget sitting in the chat; two lines are
somewhere to write — and the sides were costing the text two columns, which on a phone is the
difference. `"box"` puts the rounded border back, and anything else is refused at construction
for `local_align`'s reason.

The declarations are computed in `_input_frame_rules` rather than written into the template,
because the two shapes do not differ by a *value*: a box sets one `border`, and two rules have to
clear it and set `border-top`/`border-bottom` instead. A `border: round` left in the block would
win anyway, the declaration coming later — which is exactly how the first attempt at this rendered
a box while looking like it had set two rules. The colour is written twice, once per state, so the
test that matters is the one that **blurs** the input and looks again: wiring both to the accent is
the easy slip and nothing else in the suite ever looks away from the input.

The suggestion popup keeps its rounded box, deliberately: it is a floating list that appears over
the chat, not a place to type, and the two shapes saying two different things is the point.

**The default palette is Claude Code's**, which the chat was a WhatsApp green before. Every colour
in `ChatStyle` comes from that terminal: a warm neutral ramp — `#1f1e1d` background, `#262624` and
`#2f2e2b` surfaces, `#3d3b37` borders and the selected bubble, `#8a8984` for what is muted, and
`#f0eee6` cream to write on — with Claude's `#d97757` as the accent, on the quote border and on the
focused input. Slot 0 is that cream and slot 1 the orange, because "you in plain text, them in
orange" is the pairing the terminal itself reads by; the periwinkle, green, amber and pink behind
them are the rest of its colours. `tool_header` is the muted grey rather than a hue of its own:
a command is not a peer, and Claude Code dims a tool line rather than giving it a voice.

**Three places kept Textual's blue, and only a render showed it.** Swapping the hexes left the
chat warm and the chrome blue, because none of the three is styled the way a bubble is:

- **The scrollbar was never ours at all.** The four `scrollbar_*` fields were rendered into a
  `.scrollbar` rule — a valid selector matching nothing, so the stylesheet parsed, the fields
  looked set, and the default theme's blue ran down the side of the chat. Textual styles a
  scrollbar with `scrollbar-background`/`scrollbar-color` *properties on the scrollable widget*,
  which is what `#chat-log` carries now, and a test asserts the bar wears the palette — it fails
  on the old rule. **Its width is a field too, and one cell rather than Textual's two**:
  `scrollbar_size` renders `scrollbar-size-vertical`, and the cell it gives back goes to the
  bubbles. The test reads `scrollbar_size_vertical` — what the widget actually reserves — so it
  fails on the default rather than merely on a field being set, which is the mistake the
  `.scrollbar` rule made. Textual refuses a width below one as well, but at *mount*, in a panel
  naming a line of the stylesheet this generated; `__post_init__` refuses it where the caller
  wrote it, for `local_align`'s reason.

  **One cell is the floor, so the rest of the thinning is what the cell is painted with.** A
  terminal cannot reserve less than a cell, Textual refuses a width below one outright, and there
  is no overlay scrollbar to ask for either — `scrollbar-gutter` chooses only `auto` or `stable`,
  and both reserve the column. What was left was the *track*: a colour of its own made it a strip
  down the full height of the chat whether or not anyone was scrolling. It is `transparent` now,
  so at rest the bar is the thumb alone and the column behind it is chat. The hover and active
  colours are untouched, so the track comes back the moment the pointer reaches for it — measured,
  not assumed: `#3d3b37` under the pointer, the chat background at rest.

  **`transparent`, not `chat_bg`'s hex a second time.** Textual composites a translucent scrollbar
  background onto the parent's, so the track follows the chat wherever it is recoloured. The hex
  written twice passes the at-rest test and fails the one that recolours the chat and looks again —
  which is why that second test exists, and it was proved by writing the hex.
- **The command popup never takes focus**, the input keeps it, so Textual drew the highlighted row
  with its *blurred* block cursor. Both states are set to the accent, or the palette holds
  everywhere except the one row the eye is on.
- **The copy confirmation is Textual's own `Toast`**, floated above the chat and themed by it.
  Only `-information` is overridden; warning and error keep their colours, which mean something.

What stays Textual's is the syntax highlighting inside a fence: that is a code theme, not a chat
palette, and Claude Code's own blocks are no different.

**The header names the peer**: `21:15 @meteo · msg-3`. `ChatLog` reads the roster through the
`peers` grant, the same way it reads the conversation through `context`, and calls it fresh rather
than holding it — a peer may be registered after the widget was built. `TOOL` is named outright
because a command is in no roster, and a peer that has since gone falls back to its number: history
outlives connectors, since a backend reloads what a peer once said. `You`/`Other` told you nothing
once two connectors were in the room.

The terminal's own name is `chat`, which is a poor thing to call yourself, so `build_chat(name=…)`
overrides it — the demo is `@me`. **That assignment works only because `@connector` wrote `name`
onto the class**: `DOMNode.name` is a read-only property, and the same line on a plain `App` raises
`AttributeError`. The shadowing the fitness tests hunt for is load-bearing here, which is why
there is a test that says so; mypy sees only the property underneath, so the assignment carries a
narrow `type: ignore` explaining itself.

**One tap selects a message to reply to; two copy it.** It was a two-second hold before, and a
phone terminal takes a long press for its own menu before the application sees any of it — two taps
are a gesture nothing else is competing for.

**`event.chain` is deliberately not what decides.** Textual counts a double click only when both
land on the *exact same cell* and within half a second, which is right for a mouse and wrong for a
thumb — reaching for it would repeat the class of failure that made the long press useless here.
`_A_DOUBLE` allows 0.7s and `_A_WOBBLE` a cell of travel, and a test says so, because using the
chain count later would look like a simplification and would quietly stop working on the device
this exists for.

Selecting is a toggle, so the second tap of a pair calls it again and puts the reply target back
where it was: a double tap only copies, which is what the hold it replaced did. The press position
is still recorded in `on_mouse_down`, because a release more than `_A_DRAG` cells from the landing
was a drag and selects nothing; neither handler stops its event, or the pan underneath would have
nothing left to read.

**Two things say a press was not a tap, and a travel threshold is the weaker of them.** Textual
synthesises a `Click` from any release on the *widget* the press landed on, so dragging across a
line to select a few words — which never leaves the row it started on — arrived as a tap and
silently moved the reply target; two of them inside `_A_DOUBLE` copied the whole message.
`_A_DRAG` was widened to both axes for that, and it is not enough on its own: it has to allow a
cell or two of wobble for a thumb, so a drag selecting one or two characters slips through it —
measured, `'um'` selected and the reply retargeted anyway.

What catches that is **the selection the screen is still holding**. Textual clears it when the
press and the release share a cell, so text left selected at click time means the pointer dragged
across it, however short the drag:

| travel | selected | is it a tap? |
|---|---|---|
| 0 cells | nothing | yes — the selection was cleared, so nothing is held |
| 1 cell | `um` | no |
| 6 cells | `uma men` | no |

So the selection check is first and `_A_DRAG` is second, and they cover different gestures: a pan
selects nothing, so only the travel catches it; a short selection never travels, so only the
selection catches that. A test at travel 0 guards the guard, or a check that always fired would
take the tap with it.

**A drag is a text selection, unless it started where there is nothing to select.** From Textual 3
a mouse drag *is* a selection — the screen starts one in `_forward_event`, before the event reaches
any widget, so `event.stop()` never held it off — and `TouchScrollableContainer` was panning the log
on the same drag. Two controllers on one gesture: the selection reached for the pointer while the
pan moved the text out from under it, and the log shook. Selecting across a bubble with a mouse was
the report; the cause was older than the report.

**It cannot be split by device, and that is not a limitation of Textual.** A terminal speaks the
XTerm SGR mouse protocol and Termux turns a swipe into exactly the bytes a trackpad sends; no
protocol any terminal speaks carries the device, which is why `MouseEvent` has no field for it.
What the gesture is split by instead is *where it landed*:
`Screen.get_widget_and_offset_at` reports no content offset for a coordinate holding nothing
selectable, so a press on the margin beside a bubble pans and a press on text is Textual's to
select with. The pan then calls `clear_selection()` once, which drops the selection the screen
anchored on that same press — and, because the auto-scroll lives behind the same `_select_state`,
stops Textual reaching for the offset the pan is about to drive.

The cost is real and worth stating: **the pannable area is the background only.** On a wide
terminal that is most of the log, since the chat is centred and a bubble takes one side; on a
phone, a message long enough to fill the width leaves little to grab, and scrolling there is the
scrollbar, the wheel, or dragging to the edge — Textual's own select-auto-scroll carries the view
while a selection is open, which is now the only thing that moves the log during one.

**The pan was measured in the wrong frame from the day it was written, and nothing said so.**
`_drag_start_y` took `event.y`, which on a bubbled mouse event is relative to whatever descendant
the press first landed on — and the next report comes from a *different* descendant, because the
pan just moved one under the pointer. Traced: a press at `screen_y=8` recorded `2`, and five cells
of travel moved the log two, in a 0/1/0/1 limp. It reads `screen_y` now, which no scroll can
move. No test had ever asserted that dragging scrolls at all, which is how a feature stayed broken
through two rewrites; there is one now, and it fails on the old frame.

**The drag test was empty for a while.** It drove `pilot.mouse_down`/`mouse_up`, which do not
synthesise a `Click` — the app does that, from a release on the widget the press landed on — so
nothing reached the handler and the assertion held for the wrong reason. It builds the events by
hand now, and fails when the guard goes. Found by removing the guard and watching it pass.

The copy is confirmed by a **popup**, and it shows the text back rather than only saying a copy
happened: on a phone the clipboard cannot be checked without leaving the chat, so seeing the words
is the confirmation. `run_test` disables notifications by default, so every test that asserts on
`notify` proves only that it was *called* — there is now one that turns them on and looks for the
`Toast` on screen, because "it was called" is not "the user saw it".

**The gesture is not always reachable, so there is a key as well.** A phone terminal may take a
long press for its own selection menu before the application sees any of it, which is what Termux
does — pressing on the rendered text works in a mounted test, so what fails there is the gesture
arriving, not the handling. `copy_key` (default `ctrl+y`, validated like `quit_key`) copies the
message selected as the reply target: tap, then press.

**Copying takes two routes, because neither is enough alone.** Textual's own `copy_to_clipboard` is
OSC 52, an escape sequence a terminal is free to drop — Termux drops it — so `chat_clipboard` also
runs a **helper**: `termux-clipboard-set`, `wl-copy`, `xclip`, `xsel` or `pbcopy`, whichever the
system has. Both run every time: over SSH a helper writes the *server's* clipboard, which nobody
is looking at, and OSC 52 is what reaches the person at the keyboard. The helper is a subprocess,
so it runs in a worker rather than stopping the chat, and a failure is logged rather than raised —
the other route has already been taken, and a clipboard is never worth interrupting a conversation
for. The notification **names the routes that ran** (`Copied msg-3 (OSC 52 + termux-clipboard-set)`)
rather than claiming the text arrived; whether it did is the terminal's business, and saying which
route was taken is what makes a silent failure diagnosable. `chat_clipboard` imports nothing but
the standard library, so it is tested without mounting anything.

**Two of those tests run the helper for real**, with a working one put on `PATH`, because every
other test in the file replaces `chat_clipboard.put` with a double. Those prove the callers do the
right thing and prove nothing about the thing itself — and the wiring from `copy_message` through a
worker, an executor and `subprocess.run` is exactly where a copy can be connected wrongly and still
pass a suite full of doubles. That gap was found while chasing a report of copying not working on a
phone: the environment turned out to be healthy and the whole path sound, which nothing in the
suite had ever actually shown.

Two things were built while chasing this and then removed, because neither was a feature: a
`/copy` command that answered in the conversation, and a `diagnose.sh` that asked the machine what
the terminal could do. Both were somewhere to *read a result* when a gesture, a key and a
notification can each fail silently — worth having during the hunt, not worth carrying afterwards.
What stays is the **end-to-end test** the command hosted, moved onto `ChatLog.copy_message`: that
path runs a worker, an executor and a subprocess, and every other test of it replaces the last
step.

Three things this cost, all found by measuring rather than by reading:

- **`width: auto` collapses a bubble to four cells.** `Markdown` reports no content width of its
  own, so a container that sizes to its children sizes to nothing. The width is measured in
  `ChatLog._bubble_width` instead — the widest of the header, the body's lines and the quote, plus
  the six cells the padding and border take, capped at `bubble_max_width`. A bubble is genuinely
  dynamic now (25, 38, 54, 72 in the demo), which `width: 90%` never was.
- **A cap in cells is not a width.** `max-width: 72` let a bubble reach x=74 in a 60-column window —
  past the scrollbar and past the window itself. What keeps a bubble inside is `max-width: 100%`;
  the 72 is applied in Python, where the text is measured. `bubble_margin_right` is the separate
  gap between the bubble and the scrollbar, and it needs its own assertion: without it a bubble
  still clears the scrollbar by the log's own padding, so an edge test passes either way and guards
  nothing. That was found by breaking it.
- **`Markdown` pads and margins inside what the bubble already measured.** It carries
  `padding: 0 2 0 2` of its own, four cells the bubble's width never counted, so a line measured to
  fit wrapped anyway; and every `MarkdownParagraph` carries `margin: 0 0 1 0`, which put a second
  blank row under the text on top of the bubble's own padding. The stylesheet zeroes the padding —
  fixing the cause rather than adding four to `_BUBBLE_CHROME` — and drops the trailing margin with
  `.message-body > *:last-child`, which Textual supports, so paragraphs are still separated from
  *each other*. A bubble holding one word is five rows now, not seven.
- **The input had to stop being an `Input`.** It is single-line by construction, so there was
  nowhere to put a second line. `CommandInput` is a `TextArea`: **Enter sends; Ctrl+J, or a space
  typed before Enter, opens a line** — as do Ctrl+Enter, Shift+Enter and Alt+Enter, where the
  terminal can report them — and the
  box grows with the text up to `input_max_height`. Enter is
  claimed in `_on_key` rather than by a `Binding`, because `TextArea` inserts its newline from
  inside its own key handler and a binding is never reached. Up and Down move the suggestion
  highlight while the popup is open and the cursor between lines when it is not — a multi-line
  input needs them for both, so they delegate rather than relying on a binding falling through.

**Only `ctrl+j` is guaranteed to arrive, and the other three are the same key as Enter
underneath.** `ctrl+enter`, `shift+enter` and `alt+enter` reach Textual only through the enhanced
keyboard protocol, as `CSI 13;n u` — 13 is Return and `n-1` the modifier bitmask. Textual asks
every terminal for that protocol at startup and a terminal is free not to answer; **Termux does
not**. Then the fallbacks fail in both directions at once:

| pressed | bytes a legacy terminal sends | what Textual reports |
|---|---|---|
| Enter | `CR` `0x0D` | `enter` — sends |
| **Ctrl+J** | **`LF` `0x0A`** | **`ctrl+j` — opens a line** |
| Ctrl+Enter, Shift+Enter | `CR` `0x0D` | `enter` — **sends**, loudly wrong |
| Alt+Enter | `ESC CR` | nothing at all — silently wrong |

`ctrl+j` needs no protocol because it is not a modified Return: Line Feed has been its own byte
since teletypes, and Enter's Carriage Return is a different one. That is the whole reason it works
where the rest do not, and it is why `NEWLINE_KEYS` must never be only protocol-dependent keys —
there is a test that fails if it is, and it fails on the exact shape that shipped `ctrl+enter`
alone to a phone. Pasting multi-line text works regardless of any of this.

These are deliberately *not* in `_validate_key`'s swallowed list: that list is for keys that can
never work, and three of these four do, on a terminal that answers. One test carries both tables
above and names each degradation, because each is reported as a different bug — "it sends" and
"nothing happens" — and `pilot.press` synthesises the key name directly, so without it the suite
proves the handling and nothing at all about the wire.

**And a way in that needs no key at all: a character before Enter.** The escape is a *character*,
and Enter is the key everyone has, so nothing about it can be swallowed by a terminal.
`CommandInput._open_line_at_the_escape` consumes it and opens the line instead of sending. Claude
Code ships this too, alongside the same `ctrl+j` — independent confirmation of both, arrived at
from the bytes here and found in its docs afterwards; it ships no `ctrl+enter` at all.

**The default is a space, not the backslash Claude Code uses.** Ending a line with a space and
carrying on is what continuing already *feels* like: the gesture is the intention rather than a
code for it, which is the whole difference between a shortcut you remember and one you don't.
`build_chat(newline_escape=…)` takes any single character, or `None` to turn it off —
`validate_escape` refuses anything else, and refuses `"\n"` outright because the escape is looked
for on the cursor's own line, which never holds a newline, so it could only ever be a silent
nothing.

The check is anchored to the **cursor**, not to the end of the text, and that is not incidental: it
is the only way left to send a message that really does end in the escape — move off the end, and
Enter sends. A test says so, and the `text.endswith()` version passes the first escape test and
fails that one. With a space the cost is invisible anyway, since `submit()` strips what it sends.

`None` has no branch of its own, deliberately: no character equals it, so the comparison already
never fires. An early return for it was written, and then deleted — nothing could be broken to
make a test notice it, which is this repository's definition of code that is not earning its
place.

**Four `ctrl` combos are not keys at all**, and `_validate_key` now refuses them. A terminal sends
one byte for `ctrl+h` and for Backspace alike, so Textual reports `backspace` and a `ctrl+h`
binding never fires — which is exactly the silent nothing that validator exists to prevent, and it
was shipped as the demo's own quit key until Termux proved it. The same holds for `ctrl+i`/Tab,
`ctrl+m`/Enter and `ctrl+[`/Escape. The list is *derived* from Textual's `ANSI_SEQUENCES_KEYS`
rather than written out here, so it cannot drift from what Textual actually does; the demo quits
with `ctrl+g` now.

## The boundaries something checks

`tests/test_architecture.py` is not documentation, it is enforcement — a boundary nothing checks
is a boundary that rots. It parses the core modules and fails if:

- `textual` appears in their imports, or `openai`, `sqlalchemy`, `requests`, `httpx`;
- anything but the presentation layer imports Textual;
- the session imports the app;
- **any Textual subclass of ours takes a name that is a method on its Textual parent** — whether
  it assigns it, or is *granted* it;
- **a lazily resolved name loses its type** — every entry in `_BEHIND_AN_EXTRA` needs a matching
  import under `if TYPE_CHECKING`, or PEP 562 hands a consumer's mypy `Any` and the `py.typed` this
  package ships means nothing for it;
- **`import chatinho` needs one of the batteries** — a subprocess imports it with `textual`,
  `openai`, `sqlalchemy` and `requests` all blocked, and each of the four lazy names has to report
  its own extra;
- **`docs/SPEC.md` disagrees with the hook constants** — its summary table has to name the same
  eleven, with the same demanded method and the same grants, and each one has to have its own
  section. A spec nothing checks is a spec that rots, so adding a hook without documenting it
  fails the suite. Both halves were proved by breaking them.

That last one has bitten twice. `id` is a validated property on `DOMNode` and at least raised.
`_context` is `MessagePump`'s own context manager: shadowing it stopped the widget's message loop
with no error at all, and the only symptom was the suite going from six seconds to a timeout.
Setting `self.title` or `self.value` is ordinary use, so properties are not flagged — only the
silent case.

The grants half was added after a third near-miss: `ChatApp` was granted `run`, which is Textual's
own `App.run()` — the documented way to start the app. mypy caught it because the class annotates
its grants; one that did not would have shipped it. The grant is called `invoke` now.

## Packaging: the core installs nothing

`dependencies = []`. `ChatSession`, the eleven hooks, `HelpCommand` and `TestCommand` import nothing
but the standard library — which the fitness tests already enforced, so the packaging now says it
too. Four names live behind an extra and are resolved on first use with PEP 562 `__getattr__`:

| name | extra | brings |
|---|---|---|
| `build_chat` | `chatinho[tui]` | `textual` |
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

`__init__.py` exports 39 names: `build_chat`, `ChatSession`, `ChatMessage`, `ChatStyle`, `LOCAL`, `TOOL`;
the declaring machinery (`connector`, `tool`, `frontend`, `backend`, `require`, `hooks_of`, `options_of`,
`declares`, `declared_id`, `name_of`, `Hook`); the ten `Hook*` constants; the grant protocols (`Say`, `Ask`,
`Invoke`, `Context`, `Peers`); and the batteries (`A2AConnector`, `OpenAIConnector`,
`DatabaseBackend`, `HelpCommand`, `TestCommand`).

`ChatApp` is not exported, even though it no longer carries the underscore that used to say so:
`build_chat` is the way to build one, in `chat_builder.py`, and the class itself lives in
`chat_app.py` — a public module, reachable from it, with nothing enforcing that a caller goes
through the factory instead. The underscore was dropped once the class stopped attaching itself in
its own constructor: it takes no session, and `build_chat` hands it over as the session's
`frontend` the same way it would hand over any other peer, so there is no
longer anything privileged about instantiating it directly — only the missing `session` attribute
a caller would then have to wire up by hand, which `build_chat` still does more conveniently.

`build_chat` returns a `ChatSession`, so a consumer's mypy sees the whole surface `ChatSession`
promises — which is also why the `TYPE_CHECKING` block in `__init__.py` matters: without it the
lazy `__getattr__` hands them `Any` instead.

For a chat without a terminal, build a `ChatSession` and attach your own presentation —
`examples/headless.py` is exactly that, in about forty lines.

`ChatSession`'s own public surface is seven members: `run`, `attach`, `add_command`, `start`,
`close`, `id_of`, `forget`. `run()` is the entry point for a program whose job *is* the chat;
`start`/`close` are for driving it from inside a loop you already own.
Everything about the conversation is reached by declaring a hook — which is what
[`docs/SPEC.md`](docs/SPEC.md) specifies, hook by hook.

---

## Workflow

```bash
./setup.sh    # idempotent; auto-installs uv (handles Termux via pkg), creates .venv, uv sync
./run.sh      # runs examples/demo.py (calls setup.sh first if .venv is missing)
```

Both scripts resolve paths relative to their own location, so they work from any cwd.

**On Termux, `setup.sh` syncs `--extra tui` rather than `--extra dev`, and that is not a
preference.** PyPI ships no aarch64-Android wheel for `ruff`, nor for `openai`'s `pydantic-core`
— both are Rust — so `--extra dev` on a phone is not an install at all: it is uv handing them to
maturin and cargo to compile there. That is slow when it works, and when the cargo registry holds
a half-extracted crate it fails outright with `failed to open …/.cargo-ok: File exists`, which
reads like a chatinho problem and is not one. `tui` is textual and its pure-Python wheels, which
is the whole of what `run.sh` needs. `CHATINHO_EXTRA=dev bash setup.sh` overrides it for a phone
with a working cargo, and `CHATINHO_EXTRA` works the other way round too on a desktop.

`UV` may be pre-set to point the script at a particular uv, which is also how the Termux branch is
exercised off a phone: a stub on `PREFIX` and a stub uv show which extra each platform picks.

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
