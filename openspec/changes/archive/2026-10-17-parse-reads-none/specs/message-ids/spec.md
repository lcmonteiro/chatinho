## MODIFIED Requirements

### Requirement: Message ids are MessageID objects
A message's `id` and `reply_to` SHALL be `MessageID` objects, not strings, and every API that returns or accepts a message id (`say`, `locate`, `keep`, `link`) SHALL use `MessageID`. `str()` of a `MessageID` MUST return `msg-` followed by its hexadecimal characters, and `MessageID.parse` MUST read that text back into an equal `MessageID`, raising `ValueError` for text that is not `msg-` followed by lowercase hexadecimal characters. `MessageID.parse(None)` MUST return `None`, so a field that may hold no id is read the same way as one that always holds one. A `MessageID` MUST NOT compare equal to a string.

#### Scenario: str gives the msg- form
- **WHEN** a peer says a message
- **THEN** the returned id is a `MessageID`, not a `str`, and `str()` of it is `msg-` followed by its hexadecimal characters

#### Scenario: Round trip through text
- **WHEN** `MessageID.parse` reads `str()` of an id
- **THEN** the result equals the id and has the same hash

#### Scenario: Not an id
- **WHEN** `MessageID.parse` is given `abc`, `msg-`, or `msg-3F9A`
- **THEN** it raises `ValueError`

#### Scenario: No id
- **WHEN** `MessageID.parse` is given `None`
- **THEN** it returns `None`

#### Scenario: Archived as text
- **WHEN** the database backend archives a message and loads it back
- **THEN** its `id` and `reply_to` are `MessageID` objects equal to the ones that were archived, and a `reply_to` that was unset is still unset
