## MODIFIED Requirements

### Requirement: A reply that resolves an ask is heard, not answered
What a peer's `answer` returns SHALL be posted as an answer: addressed to nobody (`to` unset), with `reply_to` set to the question, and heard by every listener. An answer MUST NOT be handed to anyone's `answer`, whether or not an ask is waiting on it, and even when the asker both listens and answers. The same SHALL hold for the replies the session posts in a peer's name: the `ERROR` reply when its `answer` raises, and the reply saying there are too many nested asks. A peer's `answer` SHALL be called for a message exactly when the message's `to` is that peer.

#### Scenario: A peer that listens and answers asks another
- **WHEN** a peer that listens and answers is asked "go", and while answering asks another peer, which replies
- **THEN** its `answer` is called once, for "go", and it hears the reply as a listener

#### Scenario: An answer to an addressed say is heard, not answered
- **WHEN** a peer that answers says "hi" addressed to another peer that answers, and that peer's `answer` returns a reply
- **THEN** the speaker's `answer` is not called, the conversation holds exactly the say and its answer, and a speaker that listens hears the answer

#### Scenario: Two answering peers do not trade answers
- **WHEN** the only two peers that answer are A and B, and A says something that is neither addressed nor a reply
- **THEN** B's `answer` is called once, A's `answer` is never called, and the conversation holds two messages

#### Scenario: A frontend that does not answer is not asked
- **WHEN** a frontend that listens but does not declare `HookAnswer` says something addressed to a peer, and the peer answers
- **THEN** the frontend hears the answer, and the session logs no warning that a peer was asked without declaring `HookAnswer`

### Requirement: Only the asked peer resolves an ask
An `ask` that is waiting SHALL be resolved only by a reply to its question from the peer the question is addressed to (its `to`). Any other peer's reply to that question MUST be heard by the listeners like any other message, and MUST leave the ask waiting. The replies the session posts in the asked peer's name (the `ERROR` reply when its `answer` raises, and the reply saying there are too many nested asks) count as that peer's reply.

#### Scenario: A bystander replies first
- **WHEN** a peer asks `slow`, which answers after 0.2 seconds, and a third peer that listens says a reply to the question before then
- **THEN** the `ask` returns `slow`'s answer, and the conversation holds the bystander's reply as well

#### Scenario: The user answers a question put to them
- **WHEN** a peer asks the user and the user says a reply to that question
- **THEN** the `ask` returns a `Reply` holding the user's text
