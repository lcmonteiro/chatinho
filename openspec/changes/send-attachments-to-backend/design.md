# Design

## Context

See proposal.md for motivation and specs/message-attachments/spec.md for the required behavior. The current code shapes the approach in these ways:

- `ChatSession` builds every message at four sites: `say` in `_say_for`, `ask` in `_ask_for`, the command result in `_invoke_for`, and the answer reply in `_deliver`. Each passes `attachments=` into `ChatMessage` today, and each then calls `_post`.
- The session already calls backends directly, outside the queues: `_recall` finds the peer declaring `HookLoad` and awaits `load`, and `forget` does the same with `HookForget`. A backend has no peer id, so this is the only way to reach it.
- A hook is either a demand (one `method`) or a grant (`grants`), never both, and no name may be both. `_grant` builds each grant from a table of lambdas. `docs/SPEC.md`'s hook table must match the hook constants, which `tests/test_architecture.py` checks.
- The terminal renders each message body with Textual's `Markdown` (`chat_log.py`), which opens clicked links itself (`open_links=True`). `ChatLog` gets `context` and `peers` as callables from `ChatApp`.
- `DatabaseBackend` runs SQLAlchemy in an executor and has one table, `messages`. An in-memory SQLite URL is pinned to a single connection.

## Goals / Non-Goals

**Goals:**
- Attachment bytes never enter the conversation: they go from the peer that said them straight to the backend.
- Only the backend touches the file system, and only it knows where attachments live.
- The terminal opens attachment links with no configuration.

**Non-Goals:**
- An HTTP server or remote access. Links are for a browser on the same machine.
- Validating attachment names, link targets or sizes.
- Letting peers read attachment bytes. They get a link, not the content.

## Decisions

### Three hooks, following `HookLoad`/`HookForget`

| Hook | Kind | Signature | Called by |
|---|---|---|---|
| `HookKeep` | demand | `async keep(msg_id: str, attachments: Sequence[Attachment]) -> None` | the session, before posting |
| `HookLink` | demand | `async link(msg_id: str, name: str) -> Optional[str]` | the session, for `locate` |
| `HookLocate` | grant | `async locate(msg_id: str, name: str) -> Optional[str]` | any peer that declares it |

These are three hooks rather than one, because a hook carries exactly one method or grant, and `locate` must not share a name with the backend's `link`. They sit in `chat_hooks.py` next to `HookLoad`/`HookForget` ("Holding the conversation"). A `Locate` protocol is added for type checkers, as `Say` and `Ask` have.

### One keep step before every post

A private helper, `_kept(msg, attachments)`, finds the peer declaring `HookKeep` (the same lookup as `_recall`). When there are attachments, it awaits `keep(msg.id, tuple(attachments))`. It returns nothing and doesn't change the message.

The four posting sites build a text-only `ChatMessage`, call `_kept`, then `_post`. For answers and command results, the `Reply` is unwrapped in place first, as today.
- **No keeper:** the attachments are dropped (logged at debug level).
- **Keeper raises:** logged at error level, and the text is still posted, so a broken store never silences the chat.
- **Invocation messages:** built without calling `_kept`.

*Alternative considered:* keeping the attachments on `ChatMessage` and letting the backend pick them up in `listen`. Rejected, because that is exactly the design being removed: every peer would still receive the bytes.

### `locate` is routed like `forget`

`ChatSession.locate(msg_id, name)` is public, like `forget`, and `_grant` gains `locate = lambda: self.locate`, so peers and code without a peer use the same method. It finds the peer declaring `HookLink`. With none, it returns `None`. Otherwise it awaits `link(msg_id, name)`, logging any exception and returning `None`.

### `ChatMessage` loses `attachments`

The field added by `add-message-attachments` is removed. `Attachment` and `Reply` stay in `chat_message.py`. They are how peers hand attachments to the session, and what `keep` receives.

### The terminal asks, then opens or says "Not found"

- `ChatApp` declares `HookLocate` and passes `self.locate` to `ChatLog`, the same way it passes `context` and `peers`.
- `ChatLog` creates body `Markdown` widgets with `open_links=False` and handles `Markdown.LinkClicked`:
  - **absolute link** (a scheme, `/`, `//` or `#`): `app.open_url(href)`, as Textual did before
  - **relative link:** strip a leading `./`, find the message's id from the bubble's `_MessageContainer.msg_id`, and `await locate(msg_id, name)`. Then `app.open_url(link)`, or `notify("Not found")`.

Textual already percent-decodes `href`. The handler's name must not shadow a Textual method, which the architecture test already checks.

### `DatabaseBackend`: blobs in the database, files on demand

- **Storage:** a second table, `attachments`, with `msg_id`, `name`, `media_type` and `data` (a large binary). Its primary key is `(msg_id, name)`, so keeping the same attachment twice is one row, matching `messages`.
- **`keep`:** `merge`s the rows in an executor, like `listen`.
- **`link`:** reads the row. With none, it returns `None`. Otherwise it writes the data to `<cache>/_<quoted msg_id>/_<quoted name>` if not already there (quoted so no name leaves its folder, prefixed so `.` and `..` are files, not directories), and returns the file's `file://` URI (`Path.as_uri()`). The cache is a `tempfile.mkdtemp()` directory created on first use and removed with `shutil.rmtree` in `shutdown()`.
- **`forget(before)`:** deletes attachments whose `msg_id` belongs to a message being dropped. That's a subquery over `messages` with the same timestamp condition, done in the same transaction. Forgetting everything deletes all attachment rows.
- **Why blobs, not files at `keep` time:** one database stays the only store, so `forget` stays one transaction and backing up the archive is one file. Files exist only for attachments someone actually opened, and never outlive the session.

## Risks / Trade-offs

- [**BREAKING**: `ChatMessage.attachments` disappears one change after it was added] → It was merged minutes before this change was proposed, and nothing in this repository or orbe reads it yet.
- [HTML opened from `file://` runs its scripts] → Browsers give `file://` pages a unique origin with no cookies, and the content only ever comes from the chat's own peers. The README notes that attachments are untrusted content.
- [A message said before any backend existed has no attachments to link] → `locate` returns `None` and the terminal says "Not found", which is the specified behavior.
- [`keep` runs before `_post`, so a slow store delays the message] → Same trade-off as posting after the archive: correctness (the link exists when the message arrives) over latency. `DatabaseBackend` already runs its work off the event loop.
- [Large attachments in SQLite] → Acceptable for pages and small files. Size limits are a later concern for the backend.
