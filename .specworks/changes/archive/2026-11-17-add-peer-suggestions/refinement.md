# Refinement: add-peer-suggestions

## Problem

Asking one peer from the terminal means typing `@<name> text` at the start of the line, and the
person has to know and spell the peer's name exactly: a misspelt name silently becomes a say to the
whole room. Commands already solve the same problem — typing `/` opens a list of the session's
commands to pick from — but nothing helps with peers, which is where the names multiply once a chat
has more than one connector.

## Outcomes

- Typing `@` as the first character of the input opens a list of the peers that can be asked.
- The list offers only peers that answer (declare `HookAnswer`) and never the terminal itself; a
  listening-only peer such as the database backend is not offered.
- Letters typed after `@` narrow the list by prefix; a name that matches nothing, or a space after
  the name, hides it.
- Tab or Enter completes the highlighted peer as `@name ` without sending; Up/Down move the
  highlight; Escape hides the list and leaves the text as it was; with no list open Tab moves focus
  as before.
- A line completed this way and finished with text asks that peer, exactly as typing it by hand did.
- `/` and its command list behave exactly as they do today.

## Context

**Observed:**
- `frontends` capability (`src/chatinho/frontends`, living docs in `src/chatinho/frontends/docs`).
- `REQ-FRONT-002`: a line starting `@<name> text` is said addressed to the peer called *name*, with
  the text after the name only; only at the start of the line, and only when text follows.
  Implemented by `ChatFrontend._addressed` (`frontends/chat/__init__.py`), which accepts any peer
  but `LOCAL`.
- `REQ-FRONT-023` (ten scenarios): the `/` popup. `CommandSuggestions` in
  `frontends/chat/composer.py` is an `OptionList` fed by the `commands` grant; `update_for(text)`
  matches `COMMAND_PREFIX` and a token with no space; `CommandInput` reaches it by the fixed id
  `#command-suggestions` and owns the keys (`_popup_is_open`, `accept_suggestion` writes
  `/<name> `, Up/Down/Tab/Escape bindings, Enter accepts while open).
- `ChatFrontend.on_text_area_changed` calls `update_for` on every edit of the input.
- The terminal already holds `HookPeers`; `peers()` returns every registered peer by id, the
  backend included. Asking a peer that does not declare `HookAnswer` only logs a warning in the
  session — no reply ever comes.
- The popup's accent styling (both cursor states, since it never takes focus) is in
  `frontends/chat/style.py`; the mounted tests are `tests/frontends/test_command_suggestions.py`.

**Assumed:**
- Peers carry no description the way a command does, so an entry is just `@name`.
- The roster is read fresh on each keystroke, as commands are, so a peer registered later appears.

## Constraints

- [hard] Only `frontends/chat` imports Textual; the change stays inside the terminal package and
  uses the grants it already declares (`HookPeers`), no new hook.
- [hard] `REQ-FRONT-023` behaviour for `/` is unchanged.
- [hard] Addressing (`REQ-FRONT-002`) is unchanged: a typed-out `@name` of a non-answering peer is
  still accepted as today.
- [soft] One set of keys and one style for both prefixes, so `@` and `/` cannot drift apart.
- [soft] No new base class: the library keeps exactly two on purpose.

## Options

### Option A: One popup, a source per prefix

The popup generalises from commands to "suggestions": `/` takes its entries from `commands()`, `@`
from the answering peers in `peers()`, and accepting writes back the prefix that opened it.

- **Pros:** one widget, one set of key bindings, one CSS rule; `@` behaves like `/` because it is
  the same code.
- **Cons:** renames `CommandSuggestions` (and its id/test file references) to a neutral name.
- **Effort:** S
- **Touches:** `frontends`
- **Outcomes:** meets all.

### Option B: A second `PeerSuggestions` widget

A sibling popup for peers; the existing class is untouched.

- **Pros:** no rename; the command popup is not edited at all.
- **Cons:** the input must decide on every key which popup is open; keys, styling (including the
  blurred-cursor accent fix) and tests are duplicated and can drift.
- **Effort:** M
- **Touches:** `frontends`
- **Outcomes:** meets all, at the cost of the soft "cannot drift" constraint.

### Option C: A base popup with two subclasses

- **Pros:** tidy separation of the two sources.
- **Cons:** introduces a third base class, against the library's deliberate two.
- **Effort:** M
- **Touches:** `frontends`
- **Outcomes:** meets all; fails the soft no-base-class constraint.

## Recommendation

Option A, agreed with the user: one popup with a source per prefix. It meets every outcome with the
least code and keeps `/` and `@` on one implementation, so they cannot diverge.

## Open Questions

- The exact label of a peer entry (`@name` alone, or with something more) — non-blocking, settle in
  specify. (who can answer: the user)

## Candidate Capabilities

- `frontends`: modified - the terminal's input suggests answering peers after a leading `@`,
  alongside commands after `/` (extends `REQ-FRONT-023`).
