# Review: add-llm-router

Base: `main`

## Findings

- [x] R1 **test-gap** AC-ROUTE-008.3: the test makes the frontend the speaker, so 'names neither the speaker nor the frontend as a choice' is never checked for a peer that speaks; a router listing the speaker among the choices would pass (tests/routers/test_llm_router.py)
  - **Proposal**: back to test: add a case where an answering peer speaks in a room with two other answering peers, and assert the system prompt's choices list both others and not the speaker
  - **Decision**: back to test: add a case where an answering peer speaks in a room with two other answering peers, and assert the system prompt's choices list both others and not the speaker
  - done in test: added test_a_peer_that_speaks_is_not_offered_its_own_say (AC-ROUTE-008.3): a peer speaks among two answering peers and the choices are exactly the other two; it fails when answering() includes the speaker
  - confirmed in review: confirmed: the new AC-ROUTE-008.3 case asserts the choices are exactly the two other answering peers, and fails when the speaker is offered

## Changed files without tags

None: `specworks review` lists no untraced source or test file.

## Summary

The suite passes, every requirement has tagged code and every criterion a test. One test gap (R1, AC-ROUTE-008.3 never checked a speaking peer) went back to test in cycle 2 and is closed. No change to code, specs or design.
