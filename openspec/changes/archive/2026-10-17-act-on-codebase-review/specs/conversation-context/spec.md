## ADDED Requirements

### Requirement: The archive keeps each message's status
The database backend SHALL keep each message's `status` and give it back when it loads the message, so a query that leaves out failed replies leaves them out after the chat is reopened too.

#### Scenario: A failed reply, closed and reopened
- **WHEN** a peer answers the user with a reply whose status is `error`, and the chat is closed and reopened on the same database
- **THEN** the reloaded reply has status `error`, and `context(Query(errors=False))` leaves it out
