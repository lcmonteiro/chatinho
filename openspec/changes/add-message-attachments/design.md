# Design

## Context

See proposal.md for motivation and specs/message-attachments/spec.md for the required behavior. The current code shapes the approach in these ways:

- Every message is built inside `ChatSession`:
  - `say` and `ask` in `_say_for` and `_ask_for`
  - the invocation and the command's result in `_invoke_for`
  - an answer's reply in `_deliver`

  Every message goes through `_post`, which stores it and queues it. A peer never builds a `ChatMessage` that gets posted directly.
- `answer` and `execute` return `Optional[str]`. The session turns the string into a message. `ask` waits on a future that `_post` resolves with `msg.text`.
- Failures differ by path. A peer whose `answer` raises is logged by `_drain` and the chat carries on. A command that raises propagates out of `invoke` to whoever invoked it.
- The core (`chat_message.py`, `chat_session.py`, `chat_hooks.py`) imports only the standard library, and `tests/test_architecture.py` enforces this. markdown-it belongs to the `tui` extra, so the core cannot use it to find links.
- The terminal renders each message body with Textual's `Markdown` widget (`chat_log.py`, via `chat_markdown()`). Textual 8's `Markdown` opens clicked links itself unless it is created with `open_links=False`.
- `DatabaseBackend` stores `id, text, frm, to, reply_to, timestamp`.

## Goals / Non-Goals

**Goals:**
- One place that applies the attachment rules, used by every path that posts a message.
- No change for peers, commands and backends that never use attachments.

**Non-Goals:**
- Storing or serving attachments. That is a later backend change, which also decides how long links keep working. `DatabaseBackend` keeps storing text only.
- Reference-style markdown links (`[x][ref]`) and HTML `<a href>` inside messages as attachment links.
- Size limits on attachments. A serving backend can enforce them.

## Decisions

### `Attachment` and `Reply` are frozen dataclasses in `chat_message.py`

```python
@dataclass(frozen=True)
class Attachment:
    name       : str      # one relative path segment, e.g. "revenue.html"
    media_type : str      # e.g. "text/html"
    data       : bytes

@dataclass(frozen=True)
class Reply:
    text        : str
    attachments : Tuple[Attachment, ...] = ()
```

`ChatMessage` gains `attachments : Tuple[Attachment, ...] = ()` as its **last** field, so existing positional and keyword constructions still work. Tuples and frozen dataclasses keep one peer from changing what another receives: every listener gets the same message object.

Content is `bytes`, not `str`, so images and CSVs need no special case. A peer with text calls `.encode()`.

- *Alternative:* `attachments: Dict[str, bytes]` keyed by name, with the media type guessed from the extension. It reads nicely at call sites, but guessing (`.md`? `.csv`?) moves a decision the peer should make into the library.

### One rule function, applied in one place

`chat_message.py` gets a standard-library-only function:

```python
def attached(text: str, attachments: Sequence[Attachment]) -> Tuple[Attachment, ...]
```

It validates names (a single segment, unique), finds the relative link targets in `text`, raises `ValueError` for a target with no matching attachment, and returns only the linked attachments, in their original order.

`ChatSession` calls it in a small builder that every posting path uses in place of `ChatMessage(...)`: `say`, `ask`, the command result and the answer reply. The invocation message (`/name args`) is built with no attachments. Because the rule runs before `_post`, a rejected message is never stored, never queued and never resolves an `ask`.

Where the `ValueError` ends up follows the paths that already exist:
- raised to the caller of `say` or `ask`
- raised out of `invoke` for a command result
- logged by `_drain` for an `answer`

This matches the spec's scenarios without any new error handling.

### Links are found with a regex, after removing code

The core can't use markdown-it, so the rule uses a regex over inline links and images: `!?\[...\](target "optional title")`, including `<...>`-wrapped targets.

Before scanning, fenced code blocks (```` ``` ```` and `~~~`) and inline code spans are removed. Otherwise a code sample containing `[x](y.html)` would count as a link and be rejected as missing.

A target is relative when it has no URL scheme (`^[A-Za-z][A-Za-z0-9+.-]*:`), doesn't start with `/`, `//` or `#`, and has no query string. A leading `./` is stripped, and percent-escapes are decoded (`urllib.parse.unquote`) before comparing with names.

- *Why not reuse markdown-it when it's installed:* the rule would then change depending on which extras are installed. One regex, tested against the tricky cases (code spans, fences, titles, images, escaped brackets), is predictable.
- *Trade-off:* the regex is stricter than full CommonMark in rare edge cases, such as nested brackets in link text. Tests pin the supported forms, and anything outside them is simply not treated as an attachment link, so it's never silently accepted as one.

### `answer` and `execute` may return `Reply`; `ask` still returns text

The session accepts `Optional[Union[str, Reply]]` from both. A `str` is wrapped as a reply with no attachments. The future behind `ask` resolves with the reply's text, so every existing asker keeps getting a `str`. An asker that wants the attachments can read the reply message from `context()`, or take it from `listen`. This keeps `ask` backward compatible.

- *Alternative:* make `ask` return the whole message. More useful, but it changes the type every caller receives, which contradicts "no breaking changes".

### The terminal resolves links; the core computes the URL

A standard-library helper in `chat_message.py`:

```python
def attachment_url(base: Optional[str], msg: ChatMessage, href: str) -> Optional[str]
```

It returns `<base>/m/<msg.id>/<quoted name>` when `href` is a relative link to one of `msg`'s attachments. It returns `None` when there's no base URL or no such attachment. It's tested without Textual.

In the terminal:
- `chat_log.py` creates the body `Markdown` with `open_links=False`.
- The bubble handles `Markdown.LinkClicked`:
  - absolute link: open it as before, with `app.open_url`
  - attachment link: open the URL from `attachment_url`
  - otherwise: show a notice, "no attachment server is configured" or "attachment not available"
- `ChatApp` and `build_chat` take `attachment_url : Optional[str] = None` and pass it through.

The handler's name must not shadow a Textual method. `tests/test_architecture.py` already checks this.

### URL scheme `/m/<message id>/<name>`

This is the contract with the future serving backend. It's fixed here because the terminal builds these URLs. The message id plus the attachment name is unique, since names are unique within a message.

## Risks / Trade-offs

- [Messages recalled from `DatabaseBackend` have no attachments, because it stores text only] → Their relative links show "attachment not available" instead of opening. The serving backend change decides how attachments are stored and recalled.
- [Attachment content travels through every listener's queue] → Fine for pages and small files. Large payloads are the serving backend's problem, for example by storing and referencing them. No limit is added now.
- [The regex doesn't cover full CommonMark] → The supported forms are documented and tested, and an unsupported link form is ignored rather than treated as an attachment.
- [A peer that relied on `answer` returning exactly `Optional[str]` in type hints] → The hook protocols widen to `Optional[Union[str, Reply]]`. That's source compatible for implementers, and mypy stays clean because `str` is still accepted.
