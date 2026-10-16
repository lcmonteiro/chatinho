# Design

## Context

See proposal.md (Why) for the defects and their reproductions. The constraints that shape the fixes:

- **The session's routing is one function.**
  - `ChatSession._post` resolves a waiting ask: `_pending` is keyed by the question's id, and the ask is popped on any message whose `reply_to` matches.
  - `_answerer_of` decides `asked_of` for a say with no `to`. It routes to the lone answering peer, and it does not care whether the speaker is the person or the terminal speaking for itself.
  - `add_connector` takes the next number from `_next_id` without checking it is free.
- **The terminal has no channel that is not the conversation.** `ChatFrontend` reaches the person only through `say` (a message in the conversation) or Textual's `notify` (a toast). The welcome is said, so it is routed, heard and archived like anything the user types.
- **`ask` resolves a `Future[str]`.** The status of the answering message is on the message, not on the future.
- **The archive has no `status` column**, and `Base.metadata.create_all` never alters an existing table. CLAUDE.md records the policy that "an archive from before `asked_of` existed is not upgraded".
- **Lazy imports raise the "install the extra" message only when an import fails.** `chatinho.__getattr__` gives a friendly `ImportError` only when `import_module(where)` fails. `chatinho.builder` imports both frontends at the top, which is why each builder needs both extras today.

## Goals / Non-Goals

**Goals:**

- Fix every reproduced defect with the smallest change that makes its reproduction pass, and add a regression test for each that fails on today's code.
- Remove the duplication and stale text the review found, with no behaviour change beyond what the specs state.

**Non-Goals:**

- Changing `context()`'s keyword arguments, even though they overlap with `Query`. That is a wider API change worth its own proposal.
- Scoping `msg.credentials` to the answering peer. Every peer runs in-process today, so this is noted as a risk, not fixed.
- Timezone-aware archive timestamps.
- Any change to how a reply is routed (`asked_of`). Only who may *resolve* an ask changes.

## Decisions

### 1. The question's `asked_of` decides who resolves its ask

In `_post`, a reply resolves the waiting ask only when `msg.frm` equals the question's `asked_of`, looked up with `self._store.find(msg.reply_to)`. The ask stays in `_pending` until then. A non-matching reply falls through to ordinary delivery, so its listeners hear it.

- **Why `asked_of` rather than `to`:** `ask` sets both to the same value, and `asked_of` is the field the session itself owns.
- **Covers the session's own replies:** the error replies the session posts in a peer's name (raising, depth limit) already use `frm=at`, so they match without a special case.
- **Covers the user:** an ask of the user is answered by `frm == LOCAL == asked_of`.
- **Already checked:** applied to a scratch copy, this passed the full suite (595 tests) and the reproduction.
- **Alternative rejected:** keying `_pending` by `(question, peer)`. It means more state for the same check.

`McpFrontend.listen` applies the same rule. It keeps the peer id it addressed in `_Message` and ignores replies from anyone else.

### 2. Automatic numbering skips taken ids

`add_connector` advances `_next_id` past every id already in `_connectors` before using it. A pinned id that collides still raises, as today. This was checked alongside Decision 1 (595 tests passed). Rejected: a separate set of reserved ids, which the dict of connectors already is.

### 3. `PeerError` for an `error` answer

The future resolves with the answering `ChatMessage` instead of its text, and `ask` unwraps it:

- an `error` status raises `PeerError(msg.text)`;
- any other status returns the text.

The failure path that already raises keeps calling `set_exception` unchanged.

- **Where it lives:** `PeerError` is defined in `message.py` beside `ReplyStatus` and exported from `chatinho` (66 public names).
- **The agent's tools:** `AgentConnector._asking` already turns an exception into text for the model. It formats a `PeerError` with its text (the peer's own reply, already in the conversation) and keeps formatting other exceptions by type name only, as today, because those may echo a prompt.
- **Alternative rejected:** returning a `Reply` from `ask`. It changes the return type for every caller, including the ones that only want the text. Raising follows the existing contract ("an ask waiting on it raises"), just extended to the reply a peer *returned* rather than *raised*.

### 4. Status in the archive, added in place

An `ArchivedMessage.status` column: `String`, not null, default `'answered'`. In `initialize()`, after `create_all`, SQLAlchemy's `inspect(engine)` checks whether the `messages` table lacks a `status` column. If it does, a single `ALTER TABLE messages ADD COLUMN status VARCHAR NOT NULL DEFAULT 'answered'` runs. Old rows therefore load as `answered`.

- **This departs from the `asked_of` precedent on purpose.** Not upgrading would turn every existing `assistant.db` into a crash on the next launch, for a column with an obvious default.
- **CLAUDE.md** is updated to state the new policy: columns with a safe default are added in place, and nothing else is migrated.
- **Alternative rejected:** a migration framework (Alembic). It is out of proportion for one column.

### 5. The terminal's notices leave the conversation

- **Welcome:** `ChatLog` takes an optional `banner` string. It is mounted once, as a `Static` above the first message with class `chat-banner` and styled muted, and is not part of `sync()`'s window. `ChatFrontend.on_mount` no longer says the welcome.
- **Unknown command and command failure:** both become `self.notify(..., severity="warning"/"error")`.
- **Alternative rejected:** saying the notices as `TOOL`. `say` is bound to the frontend's own id, and a notice the person alone should see has no business in the archive.
- **Tests:**
  - `test_the_welcome_message_is_the_app_saying_it` and the two "Unknown command" assertions are rewritten to check the banner, the toast (with notifications enabled, as the existing toast test does) and an empty conversation.
  - A regression test with one answering peer asserts it is never asked.

### 6. Each builder beside its own frontend

- `build_chat_session` moves to `chatinho.frontends.chat`, and `build_mcp_session` to `chatinho.frontends.mcp`.
- `chatinho.builder` keeps both names through a module `__getattr__` (PEP 562) that delegates to `chatinho.__getattr__`. Reading a builder off either module therefore raises the same named `ImportError`, and `import chatinho.builder` needs nothing.
- The root's lazy table points each builder at its frontend's module, with one extra each. The `TYPE_CHECKING` imports follow, which `test_architecture` already enforces.
- **Alternative rejected:** importing inside each function body. Reading the name would then succeed and calling it would fail with a bare `ModuleNotFoundError`, which breaks the package's rule that a missing extra names itself where it is read.

### 7. One memory helper for both LLM connectors

`chatinho/connectors/memory.py` is standard library only:

- `earlier(context, memory, question) -> List[ChatMessage]` is the "limit + 1, drop the question, trim" logic both connectors repeat.
- `speaker(m, me, roster) -> Tuple[str, str]` returns a role (`assistant`/`user`) and the text, with the `name: ` prefix for other peers.

`OpenAIConnector` builds its dicts from it, and `AgentConnector` builds `AIMessage`/`HumanMessage` from it. The agent's `_parents` step stays the agent's. Adding it to OpenAI would change what that model sees, which is not this change.

### 8. Small fixes, decided here so the tasks are mechanical

- **`_validate_key(key, what)`:** takes the parameter's name for its messages.
- **Reply quote:** `_render_message` uses `preview_of(original.text)`.
- **`ChatLog.sync()`:** reads `context()` once into an id → message dict and passes it to `_render_message`.
- **Bubble widths:** `rich.cells.cell_len` replaces `len` in `_bubble_width`. `rich` comes with `textual`.
- **`DatabaseBackend.__init__`:** loses `**kwargs` and `self.config`. Python's own `TypeError` is the refusal.
- **`HelpCommand`:** drops `@require(HookSay)` and `say`.
- **`composer.py`:** imports `COMMAND_PREFIX` from `session.py` (core, standard library only) rather than defining its own.
- **`ChatFrontend._app_thread_id`:** becomes `_mounted: bool`, and `import threading` goes.

### 9. Workflow

- **CI** gains a `python-version: ["3.12", "3.13"]` matrix on the `test` job only. The lint and type-check steps are cheap, so they stay in the same job.
- **`openspec/config.yaml` `context:`** gains about ten lines: Python 3.12+, `typing` generics rather than PEP 585/604, `%`-style logging, column alignment, the three checks, and "update CLAUDE.md and docs/SPEC.md when behaviour changes".
- **OpenSpec delivery:** the duplication is generated by the CLI. The task is first to find the option of the pinned 1.13 CLI that installs skills only (`openspec init --help` / `openspec update --help`), then to regenerate and delete `.claude/commands/opsx/`.
  - If no such option exists, the task records that in the change and leaves `.claude/` as it is.
  - Hand-deleting files the next `openspec update` restores is not a fix.

## Risks / Trade-offs

- [`ask` callers that relied on receiving error text now get an exception] → Marked **BREAKING** in the proposal. In-repo callers are `AgentConnector` (handled in Decision 3) and the examples. A grep for `.ask(` across `src`, `examples` and `tests` is a task.
- [The in-place `ALTER TABLE` could fail on a backend that disallows `NOT NULL` without a default] → The default is given in the same statement, which SQLite, PostgreSQL and MySQL accept. A failure is logged, and the error propagates from `initialize()` exactly as a connection failure does today.
- [The welcome is no longer in the archive, so a reopened chat starts without it] → It is shown again by the banner on every launch, which is the point of a welcome.
- [Stricter resolution could leave an ask waiting forever if the asked peer replies under a different id] → No path posts a peer's reply under another id. `close()` still fails every waiting ask, so nothing hangs past shutdown.
- [Credentials remain readable by every listener] → Out of scope (see Non-Goals). The proposal's wording is not changed, and CLAUDE.md gets one sentence saying the scoping is by convention.

## Migration Plan

- **`ask()` callers** must catch `PeerError` where they relied on error text. The CLAUDE.md "Three verbs" section and `docs/SPEC.md`'s `HookAsk` section state this.
- **Archives** gain the `status` column on first open. Rolling back to an older chatinho still reads them, because an extra column is ignored by the older model.
- **`DatabaseBackend(..., unknown=…)` callers** remove the unknown keyword.
