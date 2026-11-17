# Review: add-peer-suggestions

Base: `main`

## Findings

- [ ] R1 **quality** Two peers sharing a name crash the terminal when `@` is typed: the popup gets two options with the id `@sol` and Textual raises DuplicateID (REQ-FRONT-029; src/chatinho/frontends/chat/composer.py:131). The session allows two peers one name, and reproduced with two `answering("sol")` peers.
  - **Proposal**: back to specify: add AC-FRONT-029.14 'Two peers sharing a name are listed once'; then the test, and the code lists each name once (sorted set) — @name already asks the first of them
  - **Decision**: back to specify: add AC-FRONT-029.14 'Two peers sharing a name are listed once'; then the test, and the code lists each name once (sorted set) — @name already asks the first of them
  - done in specify: ADDED AC-FRONT-029.14 to REQ-FRONT-029 (a shared name is listed once); tasks 2.1–2.3; design decision 'A shared name is one entry'
  - done in design: no API change: the dedupe is inside Suggestions; Interfaces unchanged
- [ ] R2 **quality** Stale docstring: on_text_area_changed still says it updates the command-suggestion popup, which now lists peers too (src/chatinho/frontends/chat/__init__.py:402)
  - **Proposal**: back to code: say 'Update the suggestion popup as the user types.'
  - **Decision**: back to code: say 'Update the suggestion popup as the user types.'

## Changed files without tags

None: `specworks review` lists no untraced source or test file. `style.py` and `tests/test_architecture.py` only follow the rename of the popup (task 1.1).

## Summary

The suite passes (839 tests) and every criterion of REQ-FRONT-029 has a test that fails without the code. Reading the diff found one crash in an untested path and one stale docstring; both are proposed, not fixed, for the next cycle.
