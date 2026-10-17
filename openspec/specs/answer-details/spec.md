# answer-details Specification

## Purpose

Makes every answer a `Reply`, which can say more than its text — that it answers with a question of its own, or that it failed — and carries that on the answer's message. Lets a say be addressed to one peer (`say(..., to=)`), and the terminal ask a peer with `@name`. Who answers a say that names nobody is the router's to decide; see `message-routing`.

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

### Requirement: A Reply reads as what it says
`str()` of a `Reply` SHALL be its text alone when its status is `answered`, and otherwise its status's value, a colon, a space and its text, so that whoever reads it as text, a model given a tool's result included, reads the answer and, when it did not answer, what it is instead. Attachments MUST NOT appear in it. `repr()` of a `Reply` MUST stay the dataclass's own.

#### Scenario: An answer reads as its text
- **WHEN** code takes `str(Reply("sunny"))`
- **THEN** it is `sunny`

#### Scenario: A question back says so
- **WHEN** code takes `str(Reply("which city?", status="asked"))`
- **THEN** it is `asked: which city?`

#### Scenario: A failure says so
- **WHEN** code takes `str(Reply("quota exceeded", status="error"))`
- **THEN** it is `error: quota exceeded`

#### Scenario: The repr is unchanged
- **WHEN** code takes `repr(Reply("sunny"))`
- **THEN** it names the text, the attachments and the status, as a dataclass's repr does

### Requirement: An answer is a Reply
A peer's `answer` SHALL return a `Reply` or `None`, as a command's `execute` does. Anything else, a plain string included, MUST be treated as a failure of that peer (`TypeError`): an `ask` waiting on it raises, and otherwise the session posts an `error` reply.

#### Scenario: A string is refused
- **WHEN** a peer's `answer` returns `"sunny"`
- **THEN** an `ask` of it raises `TypeError`, and a say asked of it gets an `error` reply

### Requirement: The status travels on the message
`ChatMessage` SHALL carry a `status`, a `ReplyStatus`, `answered` by default. The message the session posts for a peer's answer MUST carry the status of the `Reply` it came from, so anyone who hears or reads it knows what the answer said about itself. `ask` MUST return a `Reply` holding the answer's text and its status, whatever the status is, so the asker can tell an answer, a question back and a failure apart. The archive MUST keep the status.

#### Scenario: Status on the answer message
- **WHEN** a peer answers with `Reply("which city?", status="asked")`
- **THEN** the answer's message in the conversation has status `asked`

#### Scenario: Ask returns the text
- **WHEN** a peer asks with `ask(to, "weather?")` and the answer is `sunny`
- **THEN** `ask` returns a `Reply` with text `sunny` and status `answered`

#### Scenario: Ask returns a question back
- **WHEN** a peer asks with `ask(to, "weather?")` and the answer is `Reply("which city?", status="asked")`
- **THEN** `ask` returns a `Reply` with text `which city?` and status `asked`

#### Scenario: Ask returns an error answer with its status
- **WHEN** a peer asks with `ask(to, "weather?")` and the answer is `Reply("quota exceeded", status="error")`
- **THEN** `ask` returns a `Reply` with text `quota exceeded` and status `error`, and the answer is in the conversation with status `error`

### Requirement: An addressed say is asked of its peer
`say` SHALL take an optional `to`, a peer id. A say with `to` MUST be addressed to that peer: its `answer` is called, nobody waits on it, and its reply is posted with `reply_to` set to the say; everyone who listens still hears the say. A `to` that is not another peer in the chat MUST raise `ValueError`.

#### Scenario: Said to one peer
- **WHEN** a peer says "will it rain?" with `to` set to `eco`, in a room where two peers answer
- **THEN** only `eco` is asked, and its answer replies to the say

#### Scenario: Said to nobody
- **WHEN** a peer says something with `to` set to an id that is not in the chat, or to itself
- **THEN** `say` raises `ValueError`

### Requirement: The terminal asks with @name
In the terminal (`ChatFrontend`), a line that starts with `@<name>`, where `<name>` is a peer in the chat other than the terminal, followed by whitespace and some text, SHALL be an ask of that peer: it MUST be said addressed to that peer (`say(text, to=peer)`), with the text after the name only, so `@<name>` never reaches the message. Any other line, including `@<name>` alone or a name no peer has, MUST be said as typed.

#### Scenario: Asked by name
- **WHEN** the user types `@sol will it rain?` in a chat with peers `sol` and `lua`
- **THEN** only `sol` is asked, with the text `will it rain?`, and its answer replies to that message

#### Scenario: Not a peer
- **WHEN** the user types `@nobody hi`
- **THEN** `@nobody hi` is said to everyone, as typed
