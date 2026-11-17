# Review: add-llm-router

Base: `main`

## Findings

- [ ] R1 **test-gap** AC-ROUTE-008.3: the test makes the frontend the speaker, so 'names neither the speaker nor the frontend as a choice' is never checked for a peer that speaks; a router listing the speaker among the choices would pass (tests/routers/test_llm_router.py)
  - **Proposal**: back to test: add a case where an answering peer speaks in a room with two other answering peers, and assert the system prompt's choices list both others and not the speaker
  - **Decision**: back to test: add a case where an answering peer speaks in a room with two other answering peers, and assert the system prompt's choices list both others and not the speaker

## Changed files without tags

None: `specworks review` lists no untraced source or test file.

## Summary

The suite passes (867), every requirement has tagged code and every criterion a test. One test gap: AC-ROUTE-008.3's "neither the speaker" half is only checked when the speaker is the frontend.
