# Proposal: add-peer-suggestions

## Why

Asking one peer means typing its exact name after a leading `@`; a misspelt name silently becomes a
say to the whole room. Commands already get a list to pick from after `/`, and peers get nothing,
which hurts as soon as a chat has more than one connector.

## What Changes

- Typing `@` as the first character of the terminal's input opens a list of the peers that can be
  asked: those that answer, never the terminal itself.
- The list behaves like the command list: it narrows by prefix, hides on no match or a space,
  completes `@name ` with Tab or Enter without sending, moves with Up/Down and hides with Escape.
- One popup serves both prefixes (refinement option A): `/` lists commands and `@` answering peers,
  with one set of keys and one style.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `frontends`: adds REQ-FRONT-029 (peer suggestions); REQ-FRONT-023 (command suggestions) keeps
  its behaviour.

## Related requirements

- REQ-FRONT-001 left: a leading `@` with an unknown name, or with no text, is still said as typed.
- REQ-FRONT-002 left: addressing is unchanged; the list only helps type what it already accepts,
  and a typed-out `@name` of a peer that does not answer is still accepted.
- REQ-FRONT-012 left: Up still moves the cursor whenever no suggestion is open, `@` list included.
- REQ-FRONT-019 left: the header's `@name` is display only, unrelated to the input.
- REQ-FRONT-020 left: its popup is the copy confirmation, not the input's list.
- REQ-FRONT-023 left: `/` behaves exactly as it does; the shared popup is a design matter.

## Impact

- `src/chatinho/frontends/chat/composer.py`: the suggestion popup takes its entries per prefix;
  `CommandSuggestions` is renamed to a neutral name (internal to the terminal package, not exported
  from `chatinho`).
- `src/chatinho/frontends/chat/__init__.py`: hands the popup the peers as well as the commands.
- `src/chatinho/frontends/chat/style.py`: only if the popup's selector changes.
- `tests/frontends/`: new mounted tests; the command suggestion tests follow the rename.
- No new hook, dependency or extra: the terminal already declares `HookPeers`.

## Out of Scope

- An `@` anywhere but the first character of the line (no mid-sentence mentions).
- Changing who `@name` addresses, or refusing a typed-out peer that does not answer.
- Suggestions in `McpFrontend`.

Assumptions: an entry reads `@name` (peers carry no description); peers are listed sorted by name,
as commands are; the roster is read fresh on every keystroke, so a peer registered later is listed.
