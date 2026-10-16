## MODIFIED Requirements

### Requirement: Nested asks are bounded
The session SHALL track how deeply each question is nested: a question asked, or addressed with `say(to=...)` or `say(reply_to=...)`, by a peer while it answers a question of depth N has depth N + 1; any other question has depth 1. The limit SHALL be configurable on the session and default to 8. A question deeper than the limit MUST NOT reach its peer. Instead it SHALL get a reply with status `ERROR` saying there are too many nested asks, and whoever asked it receives that reply as it would any answer. A say that replies to another message and is past the limit MUST be dropped rather than answered, so error replies are never traded back and forth.

#### Scenario: A loop stops at the limit
- **WHEN** two peers answer every question by asking the other, and the user asks one of them in a session with the default limit
- **THEN** the ninth nested question gets an `ERROR` reply saying there are too many nested asks, each peer above it receives an answer, and the user's question is answered

#### Scenario: The limit is configurable
- **WHEN** the session is created with a limit of 2 and a question is nested three deep
- **THEN** the third question gets the `ERROR` reply and its peer's `answer` is not called

#### Scenario: Unrelated questions are not nested
- **WHEN** the user asks a peer twice in a row
- **THEN** both questions have depth 1

#### Scenario: Replies traded past the limit are dropped
- **WHEN** two peers answer every question by saying a reply to it, with `reply_to` set, from inside `answer`, and one of them is asked
- **THEN** the exchange stops at the limit, and no `ERROR` reply is posted for the reply that was dropped

### Requirement: A reply that resolves an ask is heard, not answered
What a peer's `answer` returns SHALL be posted as an answer: addressed to whoever asked, with `reply_to` set to the question, and heard by every listener. An answer MUST NOT be handed to anyone's `answer`, whether or not an ask is waiting on it, and even when its recipient both listens and answers. The same SHALL hold for the replies the session posts in a peer's name: the `ERROR` reply when its `answer` raises, and the reply saying there are too many nested asks. Only a message put to a peer that is not an answer SHALL reach that peer's `answer`.

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
