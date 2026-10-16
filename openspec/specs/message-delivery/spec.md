# message-delivery Specification

## Purpose

Defines how the session hands each message to the peers it is for: concurrently, without one peer's work holding up another or itself, with asks that may recurse through peers already answering, and with the frontend never left waiting.

## Requirements

### Requirement: Every delivery runs on its own
The session SHALL hand each message to each peer it is for (its listeners and, when it is addressed, its recipient) without waiting for that or any other peer to finish with an earlier message. A peer MAY therefore be inside `answer` or `listen` for several messages at once. Posting a message MUST return once the message is in the conversation, before any peer has heard or answered it. The conversation's order is the order messages were posted, whatever order peers finish in.

#### Scenario: A peer answers two questions at once
- **WHEN** two asks are put to the same peer, whose `answer` takes 0.3 seconds
- **THEN** both answers arrive in under 0.45 seconds in total

#### Scenario: A slow peer holds up nobody
- **WHEN** one peer takes 0.3 seconds to answer and another answers at once, and both are asked together
- **THEN** the fast answer arrives before the slow one, and both arrive in under 0.45 seconds in total

#### Scenario: Order is the order said
- **WHEN** a peer says two messages in a row and a listener is slower with the first than with the second
- **THEN** `context()` returns them in the order they were said

### Requirement: Asks may recurse
A peer that is answering a question SHALL be able to ask any peer, including one that is itself waiting on an answer from it, and the nested ask MUST be answered. No question waits on a peer merely because that peer is busy with another question.

#### Scenario: A asks B, and B asks A back
- **WHEN** the user asks A, A's `answer` asks B, and B's `answer` asks A before replying
- **THEN** A answers B's question, B answers A, and A answers the user, with no message left waiting

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

### Requirement: Delivery waits for start and finishes at close
A message posted before a peer is started SHALL be delivered once `start()` starts that peer, as if it had been posted then. `close()` SHALL wait up to five seconds for the deliveries in flight to finish, log a warning if they do not, and then cancel what remains. An ask whose answer is cancelled MUST fail for whoever is waiting on it rather than leave it waiting.

#### Scenario: Said before start
- **WHEN** a message is said before `start()` and a peer listens
- **THEN** the peer hears it after `start()`

#### Scenario: Close lets a listener finish
- **WHEN** a listener takes 0.1 seconds over a message and `close()` is called straight after the message is said
- **THEN** the listener has held the message by the time `close()` returns

#### Scenario: Close does not hang
- **WHEN** a peer's `answer` never returns and `close()` is called
- **THEN** `close()` returns within about five seconds, logs a warning, and whoever was waiting on that answer gets an error instead of waiting

### Requirement: The frontend never waits on others
Whatever the user sends through the frontend (text, an addressed `@peer` question, or a `/command`) SHALL return to the frontend as soon as it is posted, without waiting for any peer or command to answer. Answers arrive afterwards as messages. A question put to the user MUST keep only its asker waiting, never the frontend.

#### Scenario: A slow command does not freeze the input
- **WHEN** the user runs a command that takes one second, and then sends a message
- **THEN** running the command returns well before the command finishes, the command's invocation is shown while it runs, the message is posted before the command answers, and the command's answer then appears as a message

#### Scenario: A slow peer does not freeze the input
- **WHEN** the user asks a peer that takes one second to answer, and then says something else
- **THEN** the second message is posted before the answer arrives

#### Scenario: A question to the user
- **WHEN** a peer asks the user and waits
- **THEN** the frontend still sends what the user types and hears the other peers' messages while that peer waits

### Requirement: Connectors keep no conversation state
A connector SHALL read the conversation from the session (`context()`) rather than keeping its own copy, and the backend SHALL be the only peer that stores it. Anything a peer holds between calls, such as a client or a connection, MUST stay correct when the peer is called concurrently. The database backend MUST keep every message and attachment it is handed when they arrive concurrently.

#### Scenario: Concurrent messages are all archived
- **WHEN** fifty messages are said at once in a session with the database backend, which is then closed and reopened
- **THEN** all fifty are loaded back, in the order they were said

#### Scenario: Concurrent questions to an OpenAI-compatible model
- **WHEN** an OpenAI connector is asked three questions at once
- **THEN** each question gets its own answer, and only one client is built for its key

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

