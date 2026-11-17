# Design: clean-failing-peer-test

## Context

Only one test changes (`tests/frontends/test_mcp_frontend.py`); see proposal.md for why. No library code, criterion or shared fake changes.

## Interfaces

None: the change rewrites how one test builds its failing peer, and adds no public API (the local raising peer is a test double declared in the test file).

## Diagrams

No structural change.
