# Tasks: baseline-framework

## 1. Every peer has its own id

- [ ] 1.1 [test] Tag the existing tests that check AC-CORE-001.1 to 001.7 with `@ac` (AC-CORE-001.1, AC-CORE-001.2, AC-CORE-001.3, AC-CORE-001.4, AC-CORE-001.5, AC-CORE-001.6, AC-CORE-001.7); verify `specworks trace` lists a test for each
- [ ] 1.2 [code] Tag the code that implements it with `@req REQ-CORE-001` (REQ-CORE-001); verify `specworks trace` lists it and lint passes

## 2. A name is not an address

- [ ] 2.1 [test] Tag the existing tests that check AC-CORE-002.1 to 002.5 with `@ac` (AC-CORE-002.1, AC-CORE-002.2, AC-CORE-002.3, AC-CORE-002.4, AC-CORE-002.5); verify `specworks trace` lists a test for each
- [ ] 2.2 [code] Tag the code that implements it with `@req REQ-CORE-002` (REQ-CORE-002); verify `specworks trace` lists it and lint passes

## 3. The frontend is peer zero

- [ ] 3.1 [test] Tag the existing tests that check AC-CORE-003.1 to 003.6 with `@ac` (AC-CORE-003.1, AC-CORE-003.2, AC-CORE-003.3, AC-CORE-003.4, AC-CORE-003.5, AC-CORE-003.6); verify `specworks trace` lists a test for each
- [ ] 3.2 [code] Tag the code that implements it with `@req REQ-CORE-003` (REQ-CORE-003); verify `specworks trace` lists it and lint passes

## 4. A class declares its hooks

- [ ] 4.1 [test] Tag the existing tests that check AC-CORE-004.1 to 004.10 with `@ac` (AC-CORE-004.1, AC-CORE-004.2, AC-CORE-004.3, AC-CORE-004.4, AC-CORE-004.5, AC-CORE-004.6, AC-CORE-004.7, AC-CORE-004.8, AC-CORE-004.9, AC-CORE-004.10); verify `specworks trace` lists a test for each
- [ ] 4.2 [code] Tag the code that implements it with `@req REQ-CORE-004` (REQ-CORE-004); verify `specworks trace` lists it and lint passes

## 5. A peer gets only what it declared

- [ ] 5.1 [test] Tag the existing tests that check AC-CORE-005.1 to 005.3 with `@ac` (AC-CORE-005.1, AC-CORE-005.2, AC-CORE-005.3); verify `specworks trace` lists a test for each
- [ ] 5.2 [code] Tag the code that implements it with `@req REQ-CORE-005` (REQ-CORE-005); verify `specworks trace` lists it and lint passes

## 6. A say reaches everyone but the speaker

- [ ] 6.1 [test] Tag the existing tests that check AC-CORE-006.1 to 006.3 with `@ac` (AC-CORE-006.1, AC-CORE-006.2, AC-CORE-006.3); verify `specworks trace` lists a test for each
- [ ] 6.2 [code] Tag the code that implements it with `@req REQ-CORE-006` (REQ-CORE-006); verify `specworks trace` lists it and lint passes

## 7. An ask returns the answer

- [ ] 7.1 [test] Tag the existing tests that check AC-CORE-007.1 to 007.6 with `@ac` (AC-CORE-007.1, AC-CORE-007.2, AC-CORE-007.3, AC-CORE-007.4, AC-CORE-007.5, AC-CORE-007.6); verify `specworks trace` lists a test for each
- [ ] 7.2 [code] Tag the code that implements it with `@req REQ-CORE-007` (REQ-CORE-007); verify `specworks trace` lists it and lint passes

## 8. Only the asked peer resolves an ask

- [ ] 8.1 [test] Tag the existing tests that check AC-CORE-008.1 to 008.2 with `@ac` (AC-CORE-008.1, AC-CORE-008.2); verify `specworks trace` lists a test for each
- [ ] 8.2 [code] Tag the code that implements it with `@req REQ-CORE-008` (REQ-CORE-008); verify `specworks trace` lists it and lint passes

## 9. A say may be addressed to one peer

- [ ] 9.1 [test] Tag the existing tests that check AC-CORE-009.1 to 009.2 with `@ac` (AC-CORE-009.1, AC-CORE-009.2); verify `specworks trace` lists a test for each
- [ ] 9.2 [code] Tag the code that implements it with `@req REQ-CORE-009` (REQ-CORE-009); verify `specworks trace` lists it and lint passes

## 10. A Reply says what kind of answer it is

- [ ] 10.1 [test] Tag the existing tests that check AC-CORE-010.1 to 010.5 with `@ac` (AC-CORE-010.1, AC-CORE-010.2, AC-CORE-010.3, AC-CORE-010.4, AC-CORE-010.5); verify `specworks trace` lists a test for each
- [ ] 10.2 [code] Tag the code that implements it with `@req REQ-CORE-010` (REQ-CORE-010); verify `specworks trace` lists it and lint passes

## 11. An answer is a Reply, posted for the peer

- [ ] 11.1 [test] Tag the existing tests that check AC-CORE-011.1 to 011.4 with `@ac` (AC-CORE-011.1, AC-CORE-011.2, AC-CORE-011.3, AC-CORE-011.4); verify `specworks trace` lists a test for each
- [ ] 11.2 [code] Tag the code that implements it with `@req REQ-CORE-011` (REQ-CORE-011); verify `specworks trace` lists it and lint passes

## 12. An answer is heard, not answered

- [ ] 12.1 [test] Tag the existing tests that check AC-CORE-012.1 to 012.6 with `@ac` (AC-CORE-012.1, AC-CORE-012.2, AC-CORE-012.3, AC-CORE-012.4, AC-CORE-012.5, AC-CORE-012.6); verify `specworks trace` lists a test for each
- [ ] 12.2 [code] Tag the code that implements it with `@req REQ-CORE-012` (REQ-CORE-012); verify `specworks trace` lists it and lint passes

## 13. Commands run, they are not spoken to

- [ ] 13.1 [test] Tag the existing tests that check AC-CORE-013.1 to 013.6 with `@ac` (AC-CORE-013.1, AC-CORE-013.2, AC-CORE-013.3, AC-CORE-013.4, AC-CORE-013.5, AC-CORE-013.6); verify `specworks trace` lists a test for each
- [ ] 13.2 [code] Tag the code that implements it with `@req REQ-CORE-013` (REQ-CORE-013); verify `specworks trace` lists it and lint passes

## 14. Every delivery runs on its own

- [ ] 14.1 [test] Tag the existing tests that check AC-CORE-014.1 to 014.5 with `@ac` (AC-CORE-014.1, AC-CORE-014.2, AC-CORE-014.3, AC-CORE-014.4, AC-CORE-014.5); verify `specworks trace` lists a test for each
- [ ] 14.2 [code] Tag the code that implements it with `@req REQ-CORE-014` (REQ-CORE-014); verify `specworks trace` lists it and lint passes

## 15. Asks may recurse, to a limit

- [ ] 15.1 [test] Tag the existing tests that check AC-CORE-015.1 to 015.7 with `@ac` (AC-CORE-015.1, AC-CORE-015.2, AC-CORE-015.3, AC-CORE-015.4, AC-CORE-015.5, AC-CORE-015.6, AC-CORE-015.7); verify `specworks trace` lists a test for each
- [ ] 15.2 [code] Tag the code that implements it with `@req REQ-CORE-015` (REQ-CORE-015); verify `specworks trace` lists it and lint passes

## 16. Starting, serving and closing

- [ ] 16.1 [test] Tag the existing tests that check AC-CORE-016.1 to 016.8 with `@ac` (AC-CORE-016.1, AC-CORE-016.2, AC-CORE-016.3, AC-CORE-016.4, AC-CORE-016.5, AC-CORE-016.6, AC-CORE-016.7, AC-CORE-016.8); verify `specworks trace` lists a test for each
- [ ] 16.2 [code] Tag the code that implements it with `@req REQ-CORE-016` (REQ-CORE-016); verify `specworks trace` lists it and lint passes

## 17. Shutdown may be a coroutine

- [ ] 17.1 [test] Tag the existing tests that check AC-CORE-017.1 to 017.4 with `@ac` (AC-CORE-017.1, AC-CORE-017.2, AC-CORE-017.3, AC-CORE-017.4); verify `specworks trace` lists a test for each
- [ ] 17.2 [code] Tag the code that implements it with `@req REQ-CORE-017` (REQ-CORE-017); verify `specworks trace` lists it and lint passes

## 18. A Query says which messages

- [ ] 18.1 [test] Tag the existing tests that check AC-CORE-018.1 to 018.8 with `@ac` (AC-CORE-018.1, AC-CORE-018.2, AC-CORE-018.3, AC-CORE-018.4, AC-CORE-018.5, AC-CORE-018.6, AC-CORE-018.7, AC-CORE-018.8); verify `specworks trace` lists a test for each
- [ ] 18.2 [code] Tag the code that implements it with `@req REQ-CORE-018` (REQ-CORE-018); verify `specworks trace` lists it and lint passes

## 19. context returns the conversation

- [ ] 19.1 [test] Tag the existing tests that check AC-CORE-019.1 to 019.8 with `@ac` (AC-CORE-019.1, AC-CORE-019.2, AC-CORE-019.3, AC-CORE-019.4, AC-CORE-019.5, AC-CORE-019.6, AC-CORE-019.7, AC-CORE-019.8); verify `specworks trace` lists a test for each
- [ ] 19.2 [code] Tag the code that implements it with `@req REQ-CORE-019` (REQ-CORE-019); verify `specworks trace` lists it and lint passes

## 20. forget drops messages

- [ ] 20.1 [test] Tag the existing tests that check AC-CORE-020.1 to 020.2 with `@ac` (AC-CORE-020.1, AC-CORE-020.2); verify `specworks trace` lists a test for each
- [ ] 20.2 [code] Tag the code that implements it with `@req REQ-CORE-020` (REQ-CORE-020); verify `specworks trace` lists it and lint passes

## 21. Message ids

- [ ] 21.1 [test] Tag the existing tests that check AC-CORE-021.1 to 021.7 with `@ac` (AC-CORE-021.1, AC-CORE-021.2, AC-CORE-021.3, AC-CORE-021.4, AC-CORE-021.5, AC-CORE-021.6, AC-CORE-021.7); verify `specworks trace` lists a test for each
- [ ] 21.2 [code] Tag the code that implements it with `@req REQ-CORE-021` (REQ-CORE-021); verify `specworks trace` lists it and lint passes

## 22. The message store

- [ ] 22.1 [test] Tag the existing tests that check AC-CORE-022.1 to 022.5 with `@ac` (AC-CORE-022.1, AC-CORE-022.2, AC-CORE-022.3, AC-CORE-022.4, AC-CORE-022.5); verify `specworks trace` lists a test for each
- [ ] 22.2 [code] Tag the code that implements it with `@req REQ-CORE-022` (REQ-CORE-022); verify `specworks trace` lists it and lint passes

## 23. Attachments go to the keeper

- [ ] 23.1 [test] Tag the existing tests that check AC-CORE-023.1 to 023.8 with `@ac` (AC-CORE-023.1, AC-CORE-023.2, AC-CORE-023.3, AC-CORE-023.4, AC-CORE-023.5, AC-CORE-023.6, AC-CORE-023.7, AC-CORE-023.8); verify `specworks trace` lists a test for each
- [ ] 23.2 [code] Tag the code that implements it with `@req REQ-CORE-023` (REQ-CORE-023); verify `specworks trace` lists it and lint passes

## 24. Peers locate attachments

- [ ] 24.1 [test] Tag the existing tests that check AC-CORE-024.1 to 024.3 with `@ac` (AC-CORE-024.1, AC-CORE-024.2, AC-CORE-024.3); verify `specworks trace` lists a test for each
- [ ] 24.2 [code] Tag the code that implements it with `@req REQ-CORE-024` (REQ-CORE-024); verify `specworks trace` lists it and lint passes

## 25. Credentials ride on the message

- [ ] 25.1 [test] Tag the existing tests that check AC-CORE-025.1 to 025.3 with `@ac` (AC-CORE-025.1, AC-CORE-025.2, AC-CORE-025.3); verify `specworks trace` lists a test for each
- [ ] 25.2 [code] Tag the code that implements it with `@req REQ-CORE-025` (REQ-CORE-025); verify `specworks trace` lists it and lint passes

## 26. The workspace provider is a role

- [ ] 26.1 [test] Tag the existing tests that check AC-CORE-026.1 to 026.5 with `@ac` (AC-CORE-026.1, AC-CORE-026.2, AC-CORE-026.3, AC-CORE-026.4, AC-CORE-026.5); verify `specworks trace` lists a test for each
- [ ] 26.2 [code] Tag the code that implements it with `@req REQ-CORE-026` (REQ-CORE-026); verify `specworks trace` lists it and lint passes

## 27. The workspace grant

- [ ] 27.1 [test] Tag the existing tests that check AC-CORE-027.1 to 027.8 with `@ac` (AC-CORE-027.1, AC-CORE-027.2, AC-CORE-027.3, AC-CORE-027.4, AC-CORE-027.5, AC-CORE-027.6, AC-CORE-027.7, AC-CORE-027.8); verify `specworks trace` lists a test for each
- [ ] 27.2 [code] Tag the code that implements it with `@req REQ-CORE-027` (REQ-CORE-027); verify `specworks trace` lists it and lint passes

## 28. Where the public names live

- [ ] 28.1 [test] Tag the existing tests that check AC-CORE-028.1 to 028.7 with `@ac` (AC-CORE-028.1, AC-CORE-028.2, AC-CORE-028.3, AC-CORE-028.4, AC-CORE-028.5, AC-CORE-028.6, AC-CORE-028.7); verify `specworks trace` lists a test for each
- [ ] 28.2 [code] Tag the code that implements it with `@req REQ-CORE-028` (REQ-CORE-028); verify `specworks trace` lists it and lint passes

## 29. One builder per kind of session

- [ ] 29.1 [test] Tag the existing tests that check AC-CORE-029.1 to 029.6 with `@ac` (AC-CORE-029.1, AC-CORE-029.2, AC-CORE-029.3, AC-CORE-029.4, AC-CORE-029.5, AC-CORE-029.6); verify `specworks trace` lists a test for each
- [ ] 29.2 [code] Tag the code that implements it with `@req REQ-CORE-029` (REQ-CORE-029); verify `specworks trace` lists it and lint passes
