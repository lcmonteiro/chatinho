# Design: add-peer-suggestions

## Context

The terminal's input has one popup, `CommandSuggestions` (`src/chatinho/frontends/chat/composer.py`),
an `OptionList` fed by the `commands` grant and found by `CommandInput` through the fixed id
`#command-suggestions`. `ChatFrontend.on_text_area_changed` calls `update_for(text)` on every edit.
Addressing a peer is `ChatFrontend._addressed` (REQ-FRONT-002), which matches a literal `@`.
Motivation is in proposal.md; the chosen shape (one popup, a source per prefix) is refinement
option A.

## Goals / Non-Goals

**Goals:**
- One popup, one set of keys and one style for `/` and `@`.
- The entries for `@` come from the roster the terminal already reads (`HookPeers`).

**Non-Goals:**
- Any change to the session, the hooks, or who `@name` addresses.
- A mid-line `@`, or suggestions in `McpFrontend`.

## Decisions

### The popup holds completions, not bare names

An option's id becomes the whole completion (`/help`, `@sol`), so `take_highlighted()` returns
exactly what the input writes back (plus a space). The input no longer needs to know which prefix
opened the popup, and the key handling in `CommandInput` stays as it is. Alternative: keep bare
names and remember the active prefix — a second piece of state to keep in step with the options.
Serves: REQ-FRONT-029, REQ-FRONT-023.

### The popup is told the answering peers; it does not judge them

The popup receives a callable returning the names to offer after `@`. `ChatFrontend` supplies it:
every peer in `peers()` that is not `LOCAL` and declares `HookAnswer`, read fresh on each call so a
peer registered later appears. Keeping the `declares` check in the frontend keeps the widget a pure
list of strings, testable without a session. Alternative: hand the popup the raw `peers` grant —
it would then import the hook machinery for one filter. Serves: REQ-FRONT-029 (AC .1, .2, .6, .13).

### Same matching rule for both prefixes

The list opens only when the text starts with the prefix and holds no space yet; entries are the
names starting with the typed token, sorted. That is the existing `/` rule, now applied per prefix,
so `ask @` (AC .7) and `@sol ` (AC .5) fall out of it. Serves: REQ-FRONT-029, REQ-FRONT-023.

### Neutral names, renamed outright

`CommandSuggestions` → `Suggestions`, `SUGGESTIONS_ID` `"command-suggestions"` → `"suggestions"`,
`ChatFrontend.has_command_suggestions()` → `has_suggestions()`. All are internal to the terminal
package (none is exported from `chatinho`), so no alias is kept; the CSS selectors in `style.py`,
`tests/frontends/test_command_suggestions.py` and the two entries in `tests/test_architecture.py`
follow the rename. `PEER_PREFIX = "@"` joins `NEWLINE_ESCAPE` in `composer.py`, and `_addressed`
uses it instead of its literal. Alternative: keep the old names — a popup called "command" that
lists peers misleads the next reader.

## Interfaces

- `src/chatinho/frontends/chat/composer.py`: `PEER_PREFIX : str = "@"` (REQ-FRONT-029)
- `src/chatinho/frontends/chat/composer.py`: `SUGGESTIONS_ID : str = "suggestions"` (REQ-FRONT-023, REQ-FRONT-029)
- `src/chatinho/frontends/chat/composer.py`: `class Suggestions(OptionList)`, replacing
  `CommandSuggestions` (REQ-FRONT-023, REQ-FRONT-029):
  - `__init__(self, commands: Callable[[], Dict[str, Any]], peers: Callable[[], List[str]], **kwargs)`
  - `update_for(self, text: str) -> None`
  - `take_highlighted(self) -> Optional[str]`: the highlighted completion with its prefix
    (`"/help"`, `"@sol"`), and hides the popup; None when nothing is highlighted
  - `has_suggestions`, `hide()`, `move(delta)`: unchanged
- `src/chatinho/frontends/chat/composer.py`: `CommandInput.accept_suggestion() -> bool` writes the
  completion and a space (REQ-FRONT-023, REQ-FRONT-029)
- `src/chatinho/frontends/chat/__init__.py`: `ChatFrontend._answering_peers(self) -> List[str]`, the
  names of the peers but `LOCAL` that declare `HookAnswer` (REQ-FRONT-029)
- `src/chatinho/frontends/chat/__init__.py`: `ChatFrontend.has_suggestions(self) -> bool`, replacing
  `has_command_suggestions()` (REQ-FRONT-023, REQ-FRONT-029)

## Diagrams

No structural change: the same widgets and grants, one of them renamed and given a second source.

## Risks / Trade-offs

- [A peer and a command share a name] -> no clash: the prefix chooses the source, and the
  completion carries its prefix.
- [Reading the roster on every keystroke] -> it is a dict copy of a handful of peers, as the command
  list already is.
- [Rename breaks the `/` tests] -> they are updated in the same group, and every REQ-FRONT-023 test
  must still pass unchanged in what it asserts.

## Open Questions

None.
