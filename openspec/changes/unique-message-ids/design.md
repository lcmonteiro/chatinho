# Design

## Context

See proposal.md for motivation. `MessageStore.new_id()` (`chat_message.py`) is the only place ids are generated; every posting site in `ChatSession` calls it. It formats a counter that starts at 1 per store, under a `threading.Lock`. `DatabaseBackend._write` uses `session.merge`, keyed by `id`, so a repeated id replaces the archived row. The terminal header shows the id (`21:15 @meteo · msg-3`), and `ChatLog` sizes the header from its text.

## Goals / Non-Goals

**Goals:**
- Ids unique across sessions without asking the backend anything.
- An id is its own type, `MessageID`, not a string, so an id and arbitrary text can't be mixed up; it is still returned by `say` and still the key for replies, archives and attachments.

**Non-Goals:**
- Migrating ids already in existing archives.
- Ids that sort by time; ordering stays the `timestamp`'s job.

## Decisions

### `msg-` + 16 random hex characters

`new_id()` returns `"msg-" + secrets.token_hex(8)`. 64 bits of randomness makes a collision in a single archive negligible (about 1 in 36 million after a million messages), and needs no state, so the counter and its lock go away — `secrets` is safe to call from any thread.

- *Alternative: continue numbering after the recalled messages.* Keeps `msg-N`, but only works when `start()` recalls something: with `recall=0`, a backend without `HookLoad`, or an archive whose newest messages were forgotten, the numbers collide again. It would also need the backend to report its highest id.
- *Alternative: full `uuid4()`.* Unique too, but 32 characters doubles every id in logs, archives and `reply_to` fields for no practical gain: 64 bits already makes a collision negligible.
- *Alternative: 8 hex characters.* Too short: collisions become likely around 65,000 messages.

### `MessageID`, a frozen dataclass

`chat_message.py` gets `@dataclass(frozen=True) class MessageID` holding `hex: str`, validated as lowercase hex digits. `MessageID.new()` draws the 16 random characters, `str()` returns `"msg-" + hex`, and `MessageID.parse(text)` reads that back, raising `ValueError` otherwise. Frozen gives equality and hashing by value, so ids stay dictionary keys (`MessageStore._index`, `ChatSession._pending`, `ChatLog._msg_widgets`). It is not a `str` subclass: a string and an id never compare equal, so passing text where an id belongs is a type error to mypy rather than a lookup that quietly misses.

`parse` accepts any number of hex digits, so an archive written before this change — `msg-1`, `msg-2`, … — still loads.

`DatabaseBackend` keeps its `String` columns: it writes `str(id)` and parses on `load`. `keep`/`link` take a `MessageID` and convert at the async boundary, so the synchronous SQLAlchemy halves and the attachment file paths still work on text.

- *Alternative: a `str` subclass.* Every existing call would keep working, but an id would still equal any string that spells it, which is what this type is meant to stop.
- *Alternative: accept strings and coerce.* Keeps old callers working, but leaves two spellings of the same thing in every signature.

### A git-style short id, for display only

`MessageID.short` returns the first 7 hex characters of a 16-character id, as `git log --oneline` does; an id of any other length (one from an older archive) is shown whole, as `str()` gives it. It lives in the core (standard library only) so any presentation can use it.

The terminal uses it at the four places it shows an id: the header prefix (`ChatLog._render_message`), the reply quote (same method), the copy notice title (`ChatLog._copy_with_a_helper`) and the reply placeholder (`ChatApp._on_reply_target_change`). Nothing else changes: `_msg_widgets`, `reply_target`, `reply_to` and every hook keep the whole `MessageID`, because the terminal never takes an id typed by the user, so there is nothing a short id would need to be resolved from.

- *Alternative: 16 characters everywhere.* Headers get about 14 characters wider on every message, on screens that are often a phone in Termux.
- *Alternative: resolving short ids back to messages.* Only needed if users typed ids; they don't, so it would be unused code.

### Keep the `msg-` prefix

It keeps full ids recognisable in logs, archives and debugging output, and code that checks `startswith("msg-")` keeps working. The terminal's short id drops it, as git's short hashes drop nothing but the tail: the header already marks what the id belongs to.

## Risks / Trade-offs

- [Existing archives already hold `msg-1`, `msg-2`, …] → New ids never take that form, so they can't collide with old ones; old rows stay as they are.
- [Two short ids could look the same] → 7 hex characters (28 bits) make a clash within the screenful of messages the terminal shows (`max_displayed`, 100 by default) very unlikely, and it only affects display: the full ids behind them stay distinct, as in git.
- [Tests that expect `msg-1`] → Only two do (`tests/test_message_store.py`, `tests/test_chat_app.py`); they assert the format instead.
- [Code that passes ids as strings breaks] → Intended: it is what makes an id its own type. Inside the library every site is converted; tests that wrote ids by hand use `MessageID.parse`. mypy flags the rest.
