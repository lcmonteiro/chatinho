## MODIFIED Requirements

### Requirement: The frontend speaks for every client
The frontend SHALL handle every client itself, without adding a peer per client: for each question it receives, it MUST say the text in the session as its own message, addressed to the asked peer, remember which call it belongs to, and send that peer's reply to that message back on that call alone. A reply to the question from any other peer MUST NOT end the call. Questions from several clients MAY be open at once, and each reply MUST reach only the call whose question it answers. The frontend MUST NOT declare `HookAnswer`: nobody is at its terminal, so no peer can ask it.

#### Scenario: Two clients at once
- **WHEN** clients `lab` and `home` each ask something while the other's question still waits
- **THEN** each gets the reply to its own question, and no peer was added to the session

#### Scenario: The frontend is never asked
- **WHEN** the session counts the peers that answer
- **THEN** the frontend is not one of them

#### Scenario: Another peer replies first
- **WHEN** a client asks `weather`, and another peer that listens says a reply to the question before `weather` answers
- **THEN** the client's result is `weather`'s answer
