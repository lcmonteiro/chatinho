# Spec Delta: backends

## ADDED Requirements

### Requirement: REQ-BACK-014 The archive logs what it loads, forgets and sends

`DatabaseBackend` and `HiveBackend` SHALL log, on the `chatinho` loggers at DEBUG or INFO, each `load` with how many messages it returned, each `forget` with how many messages went, and each attachment kept or linked, by message id and name. `HiveBackend` SHALL also log each batch it sends, with how many items of each kind went and how many still wait. No record MUST hold a message's text, an attachment's content or the key; its failures keep their warnings and errors.

#### Scenario: AC-BACK-014.1 The database archive

- **GIVEN** a `DatabaseBackend` holding three messages
- **WHEN** it loads them and then forgets two
- **THEN** records hold 3 for the load and 2 for the forget

#### Scenario: AC-BACK-014.2 A batch sent to the hive

- **GIVEN** a running hive and a `HiveBackend`
- **WHEN** two messages and a trace are said and sent
- **THEN** a record names the number of messages and traces sent and how many still wait

#### Scenario: AC-BACK-014.3 Nothing said, no key

- **GIVEN** a `HiveBackend` and a `DatabaseBackend`, each capturing every `chatinho` record from DEBUG up
- **WHEN** a message with a distinctive text and an attachment is kept, loaded and forgotten by each
- **THEN** no captured record holds the text, the attachment's content or the hive's key
