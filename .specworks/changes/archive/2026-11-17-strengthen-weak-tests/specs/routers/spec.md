# Spec Delta: routers

## MODIFIED Requirements

### Requirement: REQ-ROUTE-005 SimpleRouter keeps a reply with its author

`SimpleRouter` SHALL route a say that replies to a message to whoever said that message, when it is another peer that answers, even in a room with several; a reply to the user, to a peer that does not answer, to a command's output or to oneself goes to nobody. A `to` the speaker gives always wins.

#### Scenario: AC-ROUTE-005.1 A reply to the user

- **WHEN** a peer's answer replies to the user's say
- **THEN** the lone answering peer was asked the user's say once and never the reply, and the reply is posted addressed to nobody

#### Scenario: AC-ROUTE-005.2 A follow-up

- **WHEN** the user replies to a peer's answer
- **THEN** the follow-up is addressed to that peer, which answers it

#### Scenario: AC-ROUTE-005.3 With several peers

- **WHEN** the user replies to one peer's answer in a room where two answer
- **THEN** only that peer is asked the follow-up

#### Scenario: AC-ROUTE-005.4 To a peer that does not answer

- **WHEN** the user replies to a peer that does not answer
- **THEN** the reply goes to nobody

#### Scenario: AC-ROUTE-005.5 To a command's output

- **WHEN** the user replies to what a command answered
- **THEN** the reply goes to nobody

#### Scenario: AC-ROUTE-005.6 An explicit recipient wins

- **WHEN** the user replies to one peer's answer but addresses the reply to another
- **THEN** the addressed peer is asked it

#### Scenario: AC-ROUTE-005.7 To oneself

- **WHEN** the user replies to their own message
- **THEN** the reply goes to nobody

