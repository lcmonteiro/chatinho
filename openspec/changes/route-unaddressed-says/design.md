# Design

## Context

Today `ChatSession._say_for` fills `asked_of` with `_answerer_of` (`session.py:348`). `_post` uses `asked_of` for two things: who gets the message at their `answer` (the audience), and which reply resolves a waiting `ask` (`question.asked_of == msg.frm`). Session-made answers (`_answered`, the `error` reply, the depth error) set `to = msg.frm` and leave `asked_of` unset. That is how an answer is "heard, not answered" today.

Outside the session, `asked_of` is read by `query.py:63`, `frontends/mcp.py:167`, `connectors/agent.py:218` and `backends/database.py`. `is_broadcast` is read by `connectors/agent.py:219` and `examples/hooks.py:123`.

See proposal.md for why the change is being made.

## Goals / Non-Goals

**Goals:**
- One field, `to`, decides whose `answer` is called and which reply resolves an `ask`.
- The rule that picks `to` for an unaddressed say is a replaceable object.
- With the default router, every existing chat routes as it does today, apart from the value of `to`.

**Non-Goals:**
- Shipping an LLM router. The hook makes one possible, and a later change can add it to `connectors/` or `examples/`.
- Routing to several peers at once. `route` returns one id or None.
- Migrating old archives.

## Decisions

### An answer is addressed to nobody

Without `asked_of`, `to` alone has to tell "put this to a peer's `answer`" from "this answers something". If answers kept `to = asker`, two messages that must behave differently would have the same shape:

| message | `frm` | `to` | `reply_to` → parent (`frm`, `to`) |
|---|---|---|---|
| `bot` answers the user's routed "hi" | bot | user | "hi" (user, bot) |
| the user follows up on that answer | user | bot | the answer (bot, user) |

The first must not be answered and the second must be. So answers are posted with `to = None`, and the session treats as an answer **a reply whose parent was addressed to its speaker** (`parent.to == msg.frm`). That covers a peer answering late with `say(reply_to=)` and the user answering a question a peer put to them. The follow-up in the second row then has a parent with `to = None`, so it is not an answer, and the router routes it.

Alternative: mark answers with a flag or a status. Rejected, because that is `asked_of` back under another name, and `status` already means something else (`answered` / `asked` / `error`).

### The router is a role, not a peer

A router is registered the way a command is: no id, grants bound to `TOOL`, and `initialize()`/`shutdown()` called with the commands'. A peer gets an id, and giving the router one would shift every connector's number by one for a role that is never addressed. The session holds it in `self.router`. It is given through `ChatSession(router=…)`. `build_chat_session` and `build_mcp_session` pass it through.

Alternative: one more `add_*` method. Rejected, because a chat has one router, and a constructor parameter says that.

### Where routing runs

`_say_for` decides, before `_kept` and `_post`:

1. `to` given → validated as today, no routing.
2. `frm == TOOL` → no routing.
3. `reply_to` names a message whose `to == frm` → an answer: `to = None`, no routing.
4. Otherwise `to = _checked_route(await self.router.route(msg))`. A result that is not a peer other than the speaker that declares `HookAnswer` becomes None with a warning. An exception is logged and becomes None.

The message is built with `to=None`, routed, and its `to` assigned before it is posted, so the store, listeners and the archive only ever see the routed value. `route` receives the message itself (text, `frm`, `reply_to`, credentials). Anything else it needs it reads through its own grants.

### `SimpleRouter` reads the room through grants

`SimpleRouter` declares `HookRoute`, `HookPeers` and `HookContext`. It finds the parent of a reply through `context()` by id, and the answering peers through `peers()` and `declares(..., HookAnswer)`. The frontend is `LOCAL`. This is today's `_answerer_of` moved behind the same doors any router uses, which proves the hook is enough to write it. It lives in `chatinho/routers/simple.py`, stdlib-only, and is exported.

Cost: `context()` holds only the recall window, so a reply to a message older than that is not routed to its author. Today `_store.find` has the same limit, since it searches the same store.

### `_post` and the ask

- Audience: `{msg.to}` when `to` is a connector and the message did not resolve an ask.
- Resolution: `question.to == msg.frm`.

`TOOL` invocations keep `to = TOOL`, which is not a connector, so nobody's `answer` is called for them, as today.

### Readers of the removed fields

| reader | today | after |
|---|---|---|
| `Query(peer=)` | `frm`, `to`, `asked_of`, replies to peer | `frm`, `to`, replies to peer |
| `McpFrontend.listen` | `msg.frm != question.asked_of` | `msg.frm != question.to` |
| `AgentConnector.listen` | `is_broadcast and is_local` and not asked of me | `to is None and is_local` |
| `examples/hooks.py` echo | `not is_broadcast or not is_local` | `to is not None or not is_local` |
| `DatabaseBackend` | `asked_of` column | column removed from the model |

`AgentConnector`'s "asked of me" check disappears: a say addressed to it has `to` set, so the `to is None` test already excludes it.

### The terminal sends in a worker

`ChatFrontend.on_command_input_submitted` awaits `say` inline. With a router that calls a model, that would hold Textual's message loop. The plain-text branch moves into `run_worker`, as the command branch already is. The `_repaint_after` wrap still repaints once the say is posted.

## Risks / Trade-offs

- [A listener that answered the user's says goes quiet in a one-bot room, because the say now has `to` set.] → The two in the repository are updated. `docs/SPEC.md` states the new meaning of `to is None`, and the proposal marks it **BREAKING**.
- [Old archives: answers carry `to = asker`, so a user replying to an old answer looks like an answer and is not routed.] → Accepted, since nothing is migrated (as with `status`). It affects only replies to messages written before the change. Noted in CLAUDE.md.
- [A slow router delays the say's appearance in the log.] → Covered by the terminal's worker. A router is expected to be quick, and an LLM router is the caller's choice.
- [`SimpleRouter` is the only user of `HookContext` lookups by id.] → It scans `context()`, which is at most `recall` messages. That is the same cost as `_store.find`.

## Migration Plan

One commit series on the branch, with no runtime migration. The archive model drops `asked_of`. SQLAlchemy reads and writes an old table that still has the column without complaint, because the column is nullable. Rollback is reverting the commits.
