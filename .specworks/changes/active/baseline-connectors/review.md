# Review: baseline-connectors

Base: `origin/main`

## Findings

- [x] R1 **test-gap** AC-CONN-007.2 said the server sees a client named `lab`, and AC-CONN-020.2 said the deep agent is built with `memory=["/AGENTS.md"]`; the tests assert neither: the first checks the connector's name and that it answers through the remote session, the second that what `/AGENTS.md` says reaches the model's system prompt and that at most the last five messages are remembered (`tests/connectors/test_mcp_connector.py`, `tests/connectors/test_deep_agent_connector.py`)
  - **Decision**: spec updated (ADDED REQ-CONN-007, REQ-CONN-020): both criteria now say what their tests show. AC-CONN-019.9 also gained "and was not rebuilt between the questions before", which its test asserts.

## Changed files without tags

- `.specworks/changes/active/baseline-connectors/`: this change's own artifacts.

## Summary

Ten source files and the four test files of `connectors` gained only `@req` and `@ac` comment lines: 24 requirements and 119 criteria, every one of the 123 tests tagged, no new test and no code change. Six of the tagged source files are in `support/kits/agent/` and `support/parts/memory.py`, where the agent connectors' behaviour in a chat lives. The criteria were written from the tests' names and the four OpenSpec specs; a sample of thirty tests was read in full, which corrected the three criteria above.
