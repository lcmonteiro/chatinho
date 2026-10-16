## MODIFIED Requirements

### Requirement: A say in a room with one peer that answers is asked of it
When a peer says something that is neither addressed (`to` is not set) nor a reply (`reply_to` is not set), and exactly one peer other than the speaker and the frontend declares `HookAnswer`, the session SHALL address the say to that peer: its `answer` MUST be called, and its reply posted with `reply_to` set to the say. Everyone who listens MUST still hear the say. What a command writes, and a say in a room with no such peer or with several, MUST stay a broadcast; a say that is a reply is routed as the requirement on replies says. When the peer's `answer` raises and no `ask` waits on the message, the session MUST post an `error` reply to it.

#### Scenario: One peer answers
- **WHEN** a peer says "will it rain?" and the only other peer that answers is `weather`
- **THEN** `weather`'s `answer` is called with it, and its reply comes back with `reply_to` set to the say

#### Scenario: Several peers answer
- **WHEN** a peer says something in a room where two peers answer
- **THEN** the say is a broadcast, and neither peer's `answer` is called

#### Scenario: A reply stays a reply
- **WHEN** a peer says something with `reply_to` set to a message the user said
- **THEN** it is a broadcast, even with one peer that answers

#### Scenario: A lone peer fails
- **WHEN** a say is asked of the lone peer and its `answer` raises
- **THEN** an `error` reply to the say is posted in that peer's name

## ADDED Requirements

### Requirement: A reply is asked of the peer it replies to
A say with `reply_to` set and no `to`, said by a peer and not by a command, SHALL be addressed to the author of the message it replies to when that author is a peer other than the speaker and the frontend and declares `HookAnswer`: its `answer` MUST be called, and everyone who listens MUST still hear the say. Otherwise the say MUST stay a broadcast. A say with `to` set MUST stay addressed to `to`.

#### Scenario: The user follows up on an answer
- **WHEN** the user says "hello" in a chat whose only answering peer is `bot`, `bot` answers, and the user then says "and tomorrow?" with `reply_to` set to that answer
- **THEN** `bot`'s `answer` is called with "and tomorrow?", and its reply comes back with `reply_to` set to it

#### Scenario: Following up in a room with several peers
- **WHEN** two peers answer, the user asks `sol` with `@sol`, and then replies to `sol`'s answer
- **THEN** only `sol`'s `answer` is called for the reply

#### Scenario: Replying to a peer that does not answer
- **WHEN** the user replies to a message said by a peer that only listens
- **THEN** the reply is a broadcast, and no peer's `answer` is called for it

#### Scenario: Replying to a command's output
- **WHEN** the user replies to what a command answered
- **THEN** the reply is a broadcast

#### Scenario: An explicit recipient wins
- **WHEN** the user replies to `sol`'s answer with `to` set to `lua`
- **THEN** only `lua`'s `answer` is called

#### Scenario: Replying to oneself
- **WHEN** a peer says something with `reply_to` set to a message it said itself
- **THEN** the reply is a broadcast
