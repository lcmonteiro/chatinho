## MODIFIED Requirements

### Requirement: REQ-CORE-007 An ask returns the answer

`ask(to, text)` SHALL post a message addressed to peer `to`, wait for that peer's reply, and return it as a `Reply` holding the answer's text and status, whatever the status. Asking an id that is no peer MUST raise `ValueError`. An `answer` that returns `None` leaves the ask waiting, and what the asked peer later says with `reply_to` set to the question resolves it. A peer MAY ask the user (`LOCAL`). When the asked peer's `answer` fails, the waiting `ask` MUST return the `error` reply the session posts for that failure, and MUST NOT raise the peer's error.

#### Scenario: AC-CORE-007.1 The answer comes back

- **WHEN** a peer asks another, whose `answer` returns `Reply("eco: ola")`
- **THEN** `ask` returns a `Reply` with text `eco: ola` and status `answered`

#### Scenario: AC-CORE-007.2 An unknown id

- **WHEN** a peer asks id 99 in a chat with no such peer
- **THEN** `ask` raises `ValueError`

#### Scenario: AC-CORE-007.3 Answered later

- **GIVEN** a peer whose `answer` returns `None`
- **WHEN** it later says a message with `reply_to` set to the question
- **THEN** the waiting `ask` returns that message's text

#### Scenario: AC-CORE-007.4 A peer asks the user

- **WHEN** a peer asks `LOCAL` and the frontend answers
- **THEN** `ask` returns the frontend's answer

#### Scenario: AC-CORE-007.5 The asked peer fails

- **GIVEN** a peer whose `answer` raises `RuntimeError`
- **WHEN** it is asked, and another peer is asked meanwhile
- **THEN** the first `ask` returns a `Reply` with status `error` naming the peer and `RuntimeError`, and the second returns its answer

#### Scenario: AC-CORE-007.6 A question back and a failure

- **WHEN** the answer is `Reply("which city?", status="asked")`, or `Reply("quota exceeded", status="error")`
- **THEN** `ask` returns a `Reply` with that text and that status, and an `error` answer is in the conversation with status `error`

### Requirement: REQ-CORE-011 An answer is a Reply, posted for the peer

A peer's `answer` SHALL return a `Reply` or `None`; anything else, a plain string included, MUST be treated as that peer failing with `TypeError`. The session SHALL post what `answer` returns in the peer's name: replying to the question, carrying the reply's status, and addressed to nobody. When `answer` fails, whether or not an `ask` is waiting, the session MUST post in the peer's name a reply with status `error`, replying to the question and addressed to nobody, whose text names the peer and the type of the error and never the error's message, and the chat carries on.

#### Scenario: AC-CORE-011.1 A string is refused

- **WHEN** a peer's `answer` returns a string
- **THEN** an `ask` of it returns a `Reply` with status `error` naming `TypeError`, and a say addressed to it gets an `error` reply

#### Scenario: AC-CORE-011.2 The status travels on the message

- **WHEN** a peer answers with `Reply("which city?", status="asked")`
- **THEN** the answer's message in the conversation has status `asked`

#### Scenario: AC-CORE-011.3 An answer is addressed to nobody

- **WHEN** a peer is asked and answers
- **THEN** the question's `to` is that peer, and the answer has `to` unset and `reply_to` set to the question

#### Scenario: AC-CORE-011.4 An error reply is addressed to nobody

- **GIVEN** a peer whose `answer` raises
- **WHEN** a say is addressed to it
- **THEN** the conversation holds a reply to the say with status `error` and `to` unset

#### Scenario: AC-CORE-011.5 A failed ask is in the conversation

- **GIVEN** a peer whose `answer` raises `RuntimeError("secret prompt")`
- **WHEN** it is asked
- **THEN** the conversation holds one reply to the question, from that peer, with status `error`, `to` unset, and text naming `RuntimeError` but not `secret prompt`
