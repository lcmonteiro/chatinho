## MODIFIED Requirements

### Requirement: The frontend speaks for every client
The frontend SHALL handle every client itself, without adding a peer per client: for each question it receives, it MUST say the text in the session as its own message, addressed to the asked peer, remember which call it belongs to, and send the asked peer's reply to that message back on that call alone. A reply to the question from any other peer MUST NOT end the call; the call keeps waiting for the asked peer. The replies the session posts in the asked peer's name, such as the error reply when its `answer` raises, count as that peer's. When the question can no longer be found in the conversation, the first reply to it MUST end the call, so that no call waits forever. Questions from several clients MAY be open at once, and each reply MUST reach only the call whose question it answers. The frontend MUST NOT declare `HookAnswer`: nobody is at its terminal, so no peer can ask it.

#### Scenario: Two clients at once
- **WHEN** clients `lab` and `home` each ask something while the other's question still waits
- **THEN** each gets the reply to its own question, and no peer was added to the session

#### Scenario: The frontend is never asked
- **WHEN** the session counts the peers that answer
- **THEN** the frontend is not one of them

#### Scenario: Another peer replies first
- **WHEN** a client asks `weather`, which answers after 0.2 seconds, and another peer that listens says a reply to the question before then
- **THEN** the client's result is `weather`'s answer

#### Scenario: The asked peer fails
- **WHEN** a client asks `weather` and `weather`'s `answer` raises
- **THEN** the client's call ends with a tool error saying what failed, as before
