## MODIFIED Requirements

### Requirement: context() takes a Query
The `context` grant SHALL take one optional argument, a `Query`, and return the messages it selects, oldest first; with no query it MUST return the whole conversation in reach. A `Query` MUST be the only way to narrow it: `context` MUST NOT accept `since`, `start` or `limit` as keywords, so each filter has one spelling.

#### Scenario: Unchanged without a query
- **WHEN** a peer calls `context()` in a conversation of seven messages
- **THEN** it gets all seven, oldest first

#### Scenario: The newest few
- **WHEN** a peer calls `context(Query().last(5))` in a conversation of seven messages
- **THEN** it gets the five newest, oldest first

#### Scenario: A keyword is refused
- **WHEN** a peer calls `context(limit=5)`
- **THEN** it raises `TypeError`
