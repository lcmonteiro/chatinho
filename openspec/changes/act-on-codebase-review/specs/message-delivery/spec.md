## ADDED Requirements

### Requirement: Only the asked peer resolves an ask
An `ask` that is waiting SHALL be resolved only by a reply to its question from the peer the question was asked of. Any other peer's reply to that question MUST be heard by the listeners like any other message, and MUST leave the ask waiting. The replies the session posts in the asked peer's name (the `ERROR` reply when its `answer` raises, and the reply saying there are too many nested asks) count as that peer's reply.

#### Scenario: A bystander replies first
- **WHEN** a peer asks `slow`, which answers after 0.2 seconds, and a third peer that listens says a reply to the question before then
- **THEN** the `ask` returns `slow`'s answer, and the conversation holds the bystander's reply as well

#### Scenario: The user answers a question put to them
- **WHEN** a peer asks the user and the user says a reply to that question
- **THEN** the `ask` returns the user's text

### Requirement: The terminal does not say its own notices
The terminal SHALL show its welcome text and its own notices to the person without posting them to the conversation. The welcome text MUST appear at the top of the log, but MUST NOT be a message: no peer hears it, no peer is asked it, and the archive does not keep it. Running a command that does not exist, and a command that fails, MUST be reported to the person as notifications and MUST NOT be messages. The invocation of a command that does exist, and what it answers, stay messages.

#### Scenario: The welcome with one answering peer
- **WHEN** the terminal opens with a welcome text in a chat whose only answering peer is `model`
- **THEN** the welcome text is shown, the conversation is empty, and `model`'s `answer` is not called

#### Scenario: An unknown command with one answering peer
- **WHEN** the user runs `/nope` in a chat with no such command whose only answering peer is `model`
- **THEN** the person is notified that `/nope` is unknown, the conversation holds no message about it, and `model`'s `answer` is not called

#### Scenario: A command that fails
- **WHEN** the user runs a command whose `execute` raises
- **THEN** the person is notified that it failed with the error's type, and no message says so

## MODIFIED Requirements

### Requirement: Nested asks are bounded
The session SHALL track how deeply each question is nested: a question asked, or addressed with `say(to=...)` or `say(reply_to=...)`, by a peer while it answers a question of depth N has depth N + 1; any other question has depth 1. The limit SHALL be configurable on the session and default to 8. A question deeper than the limit MUST NOT reach its peer. Instead it SHALL get a reply with status `ERROR` saying there are too many nested asks, and whoever asked it receives that reply as it would any `ERROR` answer: an `ask` waiting on it raises `PeerError`. A say that replies to another message and is past the limit MUST be dropped rather than answered, so error replies are never traded back and forth.

#### Scenario: A loop stops at the limit
- **WHEN** two peers answer every question by asking the other, and the user asks one of them in a session with the default limit
- **THEN** the ninth nested question gets an `ERROR` reply saying there are too many nested asks, the peer that asked it gets `PeerError`, and since neither peer catches it, each `answer` above it fails in turn and the user's `ask` raises `PeerError` with the same text

#### Scenario: The limit is configurable
- **WHEN** the session is created with a limit of 2 and a question is nested three deep
- **THEN** the third question gets the `ERROR` reply and its peer's `answer` is not called

#### Scenario: The asker of a question past the limit
- **WHEN** a peer asks with `ask()` a question that is past the limit
- **THEN** `ask` raises `PeerError` whose text says there are too many nested asks

#### Scenario: Unrelated questions are not nested
- **WHEN** the user asks a peer twice in a row
- **THEN** both questions have depth 1

#### Scenario: Replies traded past the limit are dropped
- **WHEN** two peers answer every question by saying a reply to it, with `reply_to` set, from inside `answer`, and one of them is asked
- **THEN** the exchange stops at the limit, and no `ERROR` reply is posted for the reply that was dropped
