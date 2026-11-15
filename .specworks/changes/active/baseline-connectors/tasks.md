# Tasks: baseline-connectors

## 1. OpenAIConnector answers with the model's text

- [ ] 1.1 [test] Tag the existing tests that check its criteria with `@ac` (AC-CONN-001.1, AC-CONN-001.2); verify `specworks trace` lists a test for each
- [ ] 1.2 [code] Tag the code that implements it with `@req REQ-CONN-001` (REQ-CONN-001); verify `specworks trace` lists it and lint passes

## 2. OpenAIConnector takes an endpoint, a model and a system prompt

- [ ] 2.1 [test] Tag the existing tests that check its criteria with `@ac` (AC-CONN-002.1, AC-CONN-002.2, AC-CONN-002.3, AC-CONN-002.4, AC-CONN-002.5); verify `specworks trace` lists a test for each
- [ ] 2.2 [code] Tag the code that implements it with `@req REQ-CONN-002` (REQ-CONN-002); verify `specworks trace` lists it and lint passes

## 3. OpenAIConnector remembers the conversation

- [ ] 3.1 [test] Tag the existing tests that check its criteria with `@ac` (AC-CONN-003.1, AC-CONN-003.2, AC-CONN-003.3, AC-CONN-003.4, AC-CONN-003.5); verify `specworks trace` lists a test for each
- [ ] 3.2 [code] Tag the code that implements it with `@req REQ-CONN-003` (REQ-CONN-003); verify `specworks trace` lists it and lint passes

## 4. A lent key wins over the configured one

- [ ] 4.1 [test] Tag the existing tests that check its criteria with `@ac` (AC-CONN-004.1, AC-CONN-004.2, AC-CONN-004.3, AC-CONN-004.4, AC-CONN-004.5, AC-CONN-004.6); verify `specworks trace` lists a test for each
- [ ] 4.2 [code] Tag the code that implements it with `@req REQ-CONN-004` (REQ-CONN-004); verify `specworks trace` lists it and lint passes

## 5. OpenAIConnector's failures are answers

- [ ] 5.1 [test] Tag the existing tests that check its criteria with `@ac` (AC-CONN-005.1, AC-CONN-005.2); verify `specworks trace` lists a test for each
- [ ] 5.2 [code] Tag the code that implements it with `@req REQ-CONN-005` (REQ-CONN-005); verify `specworks trace` lists it and lint passes

## 6. OpenAIConnector keeps one client per key

- [ ] 6.1 [test] Tag the existing tests that check its criteria with `@ac` (AC-CONN-006.1, AC-CONN-006.2, AC-CONN-006.3, AC-CONN-006.4); verify `specworks trace` lists a test for each
- [ ] 6.2 [code] Tag the code that implements it with `@req REQ-CONN-006` (REQ-CONN-006); verify `specworks trace` lists it and lint passes

## 7. McpConnector connects to one remote session

- [ ] 7.1 [test] Tag the existing tests that check its criteria with `@ac` (AC-CONN-007.1, AC-CONN-007.2, AC-CONN-007.3); verify `specworks trace` lists a test for each
- [ ] 7.2 [code] Tag the code that implements it with `@req REQ-CONN-007` (REQ-CONN-007); verify `specworks trace` lists it and lint passes

## 8. McpConnector asks the remote session when it is asked

- [ ] 8.1 [test] Tag the existing tests that check its criteria with `@ac` (AC-CONN-008.1, AC-CONN-008.2, AC-CONN-008.3, AC-CONN-008.4, AC-CONN-008.5, AC-CONN-008.6); verify `specworks trace` lists a test for each
- [ ] 8.2 [code] Tag the code that implements it with `@req REQ-CONN-008` (REQ-CONN-008); verify `specworks trace` lists it and lint passes

## 9. McpConnector answers every question once

- [ ] 9.1 [test] Tag the existing tests that check its criteria with `@ac` (AC-CONN-009.1, AC-CONN-009.2, AC-CONN-009.3, AC-CONN-009.4, AC-CONN-009.5); verify `specworks trace` lists a test for each
- [ ] 9.2 [code] Tag the code that implements it with `@req REQ-CONN-009` (REQ-CONN-009); verify `specworks trace` lists it and lint passes

## 10. McpConnector lends only what it was told to

- [ ] 10.1 [test] Tag the existing tests that check its criteria with `@ac` (AC-CONN-010.1, AC-CONN-010.2, AC-CONN-010.3, AC-CONN-010.4, AC-CONN-010.5, AC-CONN-010.6); verify `specworks trace` lists a test for each
- [ ] 10.2 [code] Tag the code that implements it with `@req REQ-CONN-010` (REQ-CONN-010); verify `specworks trace` lists it and lint passes

## 11. BasicAgentConnector is built from create_agent's parameters

- [ ] 11.1 [test] Tag the existing tests that check its criteria with `@ac` (AC-CONN-011.1, AC-CONN-011.2, AC-CONN-011.3, AC-CONN-011.4); verify `specworks trace` lists a test for each
- [ ] 11.2 [code] Tag the code that implements it with `@req REQ-CONN-011` (REQ-CONN-011); verify `specworks trace` lists it and lint passes

## 12. One question, one run of the agent

- [ ] 12.1 [test] Tag the existing tests that check its criteria with `@ac` (AC-CONN-012.1, AC-CONN-012.2, AC-CONN-012.3, AC-CONN-012.4, AC-CONN-012.5, AC-CONN-012.6, AC-CONN-012.7); verify `specworks trace` lists a test for each
- [ ] 12.2 [code] Tag the code that implements it with `@req REQ-CONN-012` (REQ-CONN-012); verify `specworks trace` lists it and lint passes

## 13. Files the agent made are attached

- [ ] 13.1 [test] Tag the existing tests that check its criteria with `@ac` (AC-CONN-013.1, AC-CONN-013.2, AC-CONN-013.3, AC-CONN-013.4, AC-CONN-013.5, AC-CONN-013.6); verify `specworks trace` lists a test for each
- [ ] 13.2 [code] Tag the code that implements it with `@req REQ-CONN-013` (REQ-CONN-013); verify `specworks trace` lists it and lint passes

## 14. The answer links its files

- [ ] 14.1 [test] Tag the existing tests that check its criteria with `@ac` (AC-CONN-014.1, AC-CONN-014.2, AC-CONN-014.3, AC-CONN-014.4, AC-CONN-014.5); verify `specworks trace` lists a test for each
- [ ] 14.2 [code] Tag the code that implements it with `@req REQ-CONN-014` (REQ-CONN-014); verify `specworks trace` lists it and lint passes

## 15. The user's says are responded to with a say

- [ ] 15.1 [test] Tag the existing tests that check its criteria with `@ac` (AC-CONN-015.1, AC-CONN-015.2, AC-CONN-015.3, AC-CONN-015.4, AC-CONN-015.5); verify `specworks trace` lists a test for each
- [ ] 15.2 [code] Tag the code that implements it with `@req REQ-CONN-015` (REQ-CONN-015); verify `specworks trace` lists it and lint passes

## 16. The chat as the agent's tools

- [ ] 16.1 [test] Tag the existing tests that check its criteria with `@ac` (AC-CONN-016.1, AC-CONN-016.2, AC-CONN-016.3, AC-CONN-016.4, AC-CONN-016.5, AC-CONN-016.6, AC-CONN-016.7, AC-CONN-016.8, AC-CONN-016.9, AC-CONN-016.10, AC-CONN-016.11, AC-CONN-016.12, AC-CONN-016.13); verify `specworks trace` lists a test for each
- [ ] 16.2 [code] Tag the code that implements it with `@req REQ-CONN-016` (REQ-CONN-016); verify `specworks trace` lists it and lint passes

## 17. The agent's memory comes from the chat

- [ ] 17.1 [test] Tag the existing tests that check its criteria with `@ac` (AC-CONN-017.1, AC-CONN-017.2, AC-CONN-017.3, AC-CONN-017.4, AC-CONN-017.5); verify `specworks trace` lists a test for each
- [ ] 17.2 [code] Tag the code that implements it with `@req REQ-CONN-017` (REQ-CONN-017); verify `specworks trace` lists it and lint passes

## 18. The agent's model may be an Endpoint

- [ ] 18.1 [test] Tag the existing tests that check its criteria with `@ac` (AC-CONN-018.1, AC-CONN-018.2, AC-CONN-018.3); verify `specworks trace` lists a test for each
- [ ] 18.2 [code] Tag the code that implements it with `@req REQ-CONN-018` (REQ-CONN-018); verify `specworks trace` lists it and lint passes

## 19. The agent's workspace as tools

- [ ] 19.1 [test] Tag the existing tests that check its criteria with `@ac` (AC-CONN-019.1, AC-CONN-019.2, AC-CONN-019.3, AC-CONN-019.4, AC-CONN-019.5, AC-CONN-019.6, AC-CONN-019.7, AC-CONN-019.8, AC-CONN-019.9); verify `specworks trace` lists a test for each
- [ ] 19.2 [code] Tag the code that implements it with `@req REQ-CONN-019` (REQ-CONN-019); verify `specworks trace` lists it and lint passes

## 20. DeepAgentConnector is built from create_deep_agent's parameters

- [ ] 20.1 [test] Tag the existing tests that check its criteria with `@ac` (AC-CONN-020.1, AC-CONN-020.2, AC-CONN-020.3, AC-CONN-020.4, AC-CONN-020.5); verify `specworks trace` lists a test for each
- [ ] 20.2 [code] Tag the code that implements it with `@req REQ-CONN-020` (REQ-CONN-020); verify `specworks trace` lists it and lint passes

## 21. A deep agent's workspace is its backend

- [ ] 21.1 [test] Tag the existing tests that check its criteria with `@ac` (AC-CONN-021.1, AC-CONN-021.2, AC-CONN-021.3, AC-CONN-021.4, AC-CONN-021.5); verify `specworks trace` lists a test for each
- [ ] 21.2 [code] Tag the code that implements it with `@req REQ-CONN-021` (REQ-CONN-021); verify `specworks trace` lists it and lint passes

## 22. A deep agent gets only the workspace tools its backend does not cover

- [ ] 22.1 [test] Tag the existing tests that check its criteria with `@ac` (AC-CONN-022.1, AC-CONN-022.2, AC-CONN-022.3); verify `specworks trace` lists a test for each
- [ ] 22.2 [code] Tag the code that implements it with `@req REQ-CONN-022` (REQ-CONN-022); verify `specworks trace` lists it and lint passes

## 23. A deep agent is told where things are

- [ ] 23.1 [test] Tag the existing tests that check its criteria with `@ac` (AC-CONN-023.1); verify `specworks trace` lists a test for each
- [ ] 23.2 [code] Tag the code that implements it with `@req REQ-CONN-023` (REQ-CONN-023); verify `specworks trace` lists it and lint passes

## 24. DeepAgentConnector is the same peer in the chat

- [ ] 24.1 [test] Tag the existing tests that check its criteria with `@ac` (AC-CONN-024.1, AC-CONN-024.2, AC-CONN-024.3, AC-CONN-024.4); verify `specworks trace` lists a test for each
- [ ] 24.2 [code] Tag the code that implements it with `@req REQ-CONN-024` (REQ-CONN-024); verify `specworks trace` lists it and lint passes
