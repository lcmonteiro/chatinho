# answer-details Specification

## Purpose

Makes every answer a `Reply`, which can say more than its text — that it answers with a question of its own, or that it failed — and carries that on the answer's message. Lets a say be addressed to one peer (`say(..., to=)`), and the terminal ask a peer with `@name`. Makes a room with one peer that answers behave as a conversation with it: a say there is asked of that peer.

## Requirements

### Requirement: Answer status
`Reply` SHALL accept an optional `status`, a `ReplyStatus` enum (a `str` enum, so its value is accepted too), one of `answered` (the default), `asked` (the answer is a question back to the asker, for example when more information is needed) and `error` (the peer could not answer). A peer that does not know MUST answer `answered`, saying so in the text. A `Reply` without a status MUST count as `answered`. Any other status MUST be refused with `ValueError` when the `Reply` is created.

#### Scenario: Plain answer
- **WHEN** a peer's `answer` returns `Reply("sunny")`
- **THEN** the answer's status is `answered`

#### Scenario: Answered with a question
- **WHEN** a peer's `answer` returns `Reply("Which login flow?", status="asked")`
- **THEN** the answer's status is `asked` and its text is `Which login flow?`

#### Scenario: Peer reports an error
- **WHEN** a peer's `answer` returns `Reply("the forecast service is down", status="error")`
- **THEN** the answer's status is `error`

#### Scenario: Invalid status
- **WHEN** code creates `Reply("x", status="maybe")`
- **THEN** it raises `ValueError`

### Requirement: An answer is a Reply
A peer's `answer` SHALL return a `Reply` or `None`, as a command's `execute` does. Anything else, a plain string included, MUST be treated as a failure of that peer (`TypeError`): an `ask` waiting on it raises, and otherwise the session posts an `error` reply.

#### Scenario: A string is refused
- **WHEN** a peer's `answer` returns `"sunny"`
- **THEN** an `ask` of it raises `TypeError`, and a say asked of it gets an `error` reply

### Requirement: The status travels on the message
`ChatMessage` SHALL carry a `status`, a `ReplyStatus`, `answered` by default. The message the session posts for a peer's answer MUST carry the status of the `Reply` it came from, so anyone who hears or reads it knows what the answer said about itself. `ask` MUST keep returning the answer's text. The archive need not keep the status.

#### Scenario: Status on the answer message
- **WHEN** a peer answers with `Reply("which city?", status="asked")`
- **THEN** the answer's message in the conversation has status `asked`

#### Scenario: Ask returns the text
- **WHEN** a peer asks with `ask(to, "weather?")` and the answer is `sunny`
- **THEN** `ask` returns `sunny`

### Requirement: An addressed say is asked of its peer
`say` SHALL take an optional `to`, a peer id. A say with `to` MUST be addressed to that peer: its `answer` is called, nobody waits on it, and its reply is posted with `reply_to` set to the say; everyone who listens still hears the say. A `to` that is not another peer in the chat MUST raise `ValueError`.

#### Scenario: Said to one peer
- **WHEN** a peer says "will it rain?" with `to` set to `eco`, in a room where two peers answer
- **THEN** only `eco` is asked, and its answer replies to the say

#### Scenario: Said to nobody
- **WHEN** a peer says something with `to` set to an id that is not in the chat, or to itself
- **THEN** `say` raises `ValueError`

### Requirement: The terminal asks with @name
In the terminal (`ChatApp`), a line that starts with `@<name>`, where `<name>` is a peer in the chat other than the terminal, followed by whitespace and some text, SHALL be an ask of that peer: it MUST be said addressed to that peer (`say(text, to=peer)`), with the text after the name only, so `@<name>` never reaches the message. Any other line, including `@<name>` alone or a name no peer has, MUST be said as typed.

#### Scenario: Asked by name
- **WHEN** the user types `@sol will it rain?` in a chat with peers `sol` and `lua`
- **THEN** only `sol` is asked, with the text `will it rain?`, and its answer replies to that message

#### Scenario: Not a peer
- **WHEN** the user types `@nobody hi`
- **THEN** `@nobody hi` is said to everyone, as typed

### Requirement: A say in a room with one peer that answers is asked of it
When a peer says something that is neither addressed (`to` is not set) nor a reply (`reply_to` is not set), and exactly one peer other than the speaker and the frontend declares `HookAnswer`, the session SHALL address the say to that peer: its `answer` MUST be called, and its reply posted with `reply_to` set to the say. Everyone who listens MUST still hear the say. What a command writes, a say that is a reply, and a say in a room with no such peer or with several MUST stay a broadcast. When the peer's `answer` raises and no `ask` waits on the message, the session MUST post an `error` reply to it.

#### Scenario: One peer answers
- **WHEN** a peer says "will it rain?" and the only other peer that answers is `weather`
- **THEN** `weather`'s `answer` is called with it, and its reply comes back with `reply_to` set to the say

#### Scenario: Several peers answer
- **WHEN** a peer says something in a room where two peers answer
- **THEN** the say is a broadcast, and neither peer's `answer` is called

#### Scenario: A reply stays a reply
- **WHEN** a peer says something with `reply_to` set
- **THEN** it is a broadcast, even with one peer that answers

#### Scenario: A lone peer fails
- **WHEN** a say is asked of the lone peer and its `answer` raises
- **THEN** an `error` reply to the say is posted in that peer's name
