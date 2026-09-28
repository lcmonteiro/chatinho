# Design

## Context

See proposal.md for motivation. `MessageStore.new_id()` (`chat_message.py`) is the only place ids are generated; every posting site in `ChatSession` calls it. It formats a counter that starts at 1 per store, under a `threading.Lock`. `DatabaseBackend._write` uses `session.merge`, keyed by `id`, so a repeated id replaces the archived row. The terminal header shows the id (`21:15 @meteo · msg-3`), and `ChatLog` sizes the header from its text.

## Goals / Non-Goals

**Goals:**
- Ids unique across sessions without asking the backend anything.
- No change to how ids are used: still strings, still returned by `say`/`ask`, still the key for replies and archives.

**Non-Goals:**
- Migrating ids already in existing archives.
- A shorter display form of the id in the terminal header.
- Ids that sort by time; ordering stays the `timestamp`'s job.

## Decisions

### `msg-` + 16 random hex characters

`new_id()` returns `"msg-" + secrets.token_hex(8)`. 64 bits of randomness makes a collision in a single archive negligible (about 1 in 36 million after a million messages), and needs no state, so the counter and its lock go away — `secrets` is safe to call from any thread.

- *Alternative: continue numbering after the recalled messages.* Keeps `msg-N`, but only works when `start()` recalls something: with `recall=0`, a backend without `HookLoad`, or an archive whose newest messages were forgotten, the numbers collide again. It would also need the backend to report its highest id.
- *Alternative: full `uuid4()`.* Unique too, but 32 characters makes every terminal header noticeably wider for no practical gain over 16.
- *Alternative: 8 hex characters.* Too short: collisions become likely around 65,000 messages.

### Keep the `msg-` prefix

It keeps ids recognisable in logs and headers, and code that checks `startswith("msg-")` keeps working.

## Risks / Trade-offs

- [Existing archives already hold `msg-1`, `msg-2`, …] → New ids never take that form, so they can't collide with old ones; old rows stay as they are.
- [Wider header in the terminal] → `ChatLog` already sizes the header to its text, so it grows by about 14 characters; a shorter display is a separate change.
- [Tests that expect `msg-1`] → Only two do (`tests/test_message_store.py`, `tests/test_chat_app.py`); they assert the format instead.
