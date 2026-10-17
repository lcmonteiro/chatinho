## MODIFIED Requirements

### Requirement: The user's says are responded to with a say
What the user says with `to` unset SHALL be responded to with a say from the connector replying to it, holding the same text and attachments a question would get. What other peers say with `to` unset MUST NOT be responded to; it reaches the agent only through memory. A message addressed to the connector (its `to` is the connector), including a say the router gave it, MUST be answered as a question, never also responded to as a say. A message addressed to any other peer MUST NOT be responded to. When the run fails, the response MUST be a say naming the connector and the kind of failure.

#### Scenario: The user says something to everyone
- **WHEN** the user says "Draw the login flow" with `to` unset, and the agent answers "Here: [Login](login.svg)" after a tool made `login.svg`
- **THEN** the connector says "Here: [Login](login.svg)" replying to the user's message, with `login.svg` attached

#### Scenario: Another peer says something to everyone
- **WHEN** another peer says "hello" with `to` unset
- **THEN** the connector says nothing and the model is not called

#### Scenario: Asked directly
- **WHEN** the user asks the connector a question addressed to it
- **THEN** the model runs once and the connector answers with one reply, without also saying anything

#### Scenario: The run fails on a say
- **WHEN** the user says something with `to` unset and the model raises
- **THEN** the connector says a message naming itself and the error's type, replying to the user's message

#### Scenario: The only answering peer
- **WHEN** the connector is the only answering peer and the user says something without addressing it
- **THEN** the router addresses the say to the connector, the model runs once, and the connector answers with one reply without also saying anything
