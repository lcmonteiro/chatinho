## ADDED Requirements

### Requirement: forget drops from the conversation too
`ChatSession.forget(before)` SHALL drop the messages stamped before `before` from the session's conversation, and every message when `before` is None, whether or not a backend declares `HookForget`; afterwards `context()` MUST NOT return them. It SHALL also ask the backend that declares `HookForget` to drop them from the archive, and MUST return the number the backend reports, or 0 when there is no such backend.

#### Scenario: Forgotten here, not only in the archive
- **WHEN** a session with the database backend holds three messages, and `forget(before=t)` is called with `t` after the first two
- **THEN** `context()` returns only the third, and `forget` returns 2

#### Scenario: Without a backend
- **WHEN** a session without a backend holds two messages and `forget()` is called
- **THEN** `context()` returns nothing, and `forget` returns 0
