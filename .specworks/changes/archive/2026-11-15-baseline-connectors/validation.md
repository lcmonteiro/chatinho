# Validation: baseline-connectors

## Findings

<!-- One finding per failed blocking check, written by `specworks validate --write`,
plus any added with `specworks finding add ... --artifact validation`.
`- [ ] V<n>` while open, `- [x] V<n>` once validate confirmed it.
Write "None." when there are no findings. -->

- [x] V1 **test-gap** AC-CONN-020.1 says the deep agent is built with the given subagent, but its test (tests/connectors/test_deep_agent_connector.py, test_deep_agents_options_reach_the_agent) only asserts that the model is offered the `task` tool. deep agents adds a general-purpose subagent by default, so `task` is offered with no `subagents` at all (measured: a DeepAgentConnector with no options has ls, read_file, write_file, edit_file, delete, glob, grep, task): the test passes whether or not `subagents` reaches create_deep_agent, and nothing else checks that REQ-CONN-020 passes deep agents' options on
  - **Proposal**: back to review: decide between making the test tell the two apart (for instance asserting that the `task` tool's description names `researcher`, which is absent by default) and rewording AC-CONN-020.1 to what the test shows; as it stands the criterion has no test that checks it
  - confirmed in validate: spec updated (ADDED REQ-CONN-020): AC-CONN-020.1 now says what its test shows, that the option is accepted, the connector answers and the agent has the task tool; the user chose to reword rather than change an existing test in a baseline, and the test is noted as weak for a later change
- [x] V2 **spec-gap** AC-CONN-020.2 says the run is given at most the chat's last five messages before the question, but with `memory=Query().last(5)` the model receives six: the five selected plus the parent of its own answer whose question fell out of the window (AgentPeer._parents in src/chatinho/support/kits/agent/peer.py; measured: question 2, ok, question 3, ok, question 4, ok, then question 5). The test allows it (`len(remembered) <= 7`, and its comment says so), so the criterion states something the code does not do and the test does not assert; REQ-CONN-017 states the parent rule only for a say of the user, and here the parent is a question asked of the agent
  - **Proposal**: back to review: reword AC-CONN-020.2 (and REQ-CONN-017 if the parent rule is meant to cover any message the agent replied to) so it says what the run is given: the five messages the query selects, plus the message one of its own answers replies to when the query left it out
  - confirmed in validate: spec updated (ADDED REQ-CONN-017, REQ-CONN-020): REQ-CONN-017 now states the parent rule for any message the agent replied to, a question that fell out of the query's limit included, and AC-CONN-020.2 no longer says five

## Summary

Verdict: PASS (0 critical, 1 warnings)

- Completeness 11/11
- Correctness 7/8
- Coherence 3/3

Warnings:
- the specs are the ones agreed when specify passed: REQ-CONN-007 changed; REQ-CONN-017 changed; REQ-CONN-019 changed; REQ-CONN-020 changed; if that is intended, `specworks start design --change baseline-connectors` re-checks specify and accepts them; the tests and code then follow the new specs
