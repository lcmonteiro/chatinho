## MODIFIED Requirements

### Requirement: The status travels on the message
`ChatMessage` SHALL carry a `status`, a `ReplyStatus`, `answered` by default. The message the session posts for a peer's answer MUST carry the status of the `Reply` it came from, so anyone who hears or reads it knows what the answer said about itself. `ask` MUST return the answer's text when its status is `answered` or `asked`, and MUST raise `PeerError` when its status is `error`; the error's text MUST be the answer's text. `PeerError` SHALL be importable from `chatinho`. The archive MUST keep the status.

#### Scenario: Status on the answer message
- **WHEN** a peer answers with `Reply("which city?", status="asked")`
- **THEN** the answer's message in the conversation has status `asked`

#### Scenario: Ask returns the text
- **WHEN** a peer asks with `ask(to, "weather?")` and the answer is `sunny`
- **THEN** `ask` returns `sunny`

#### Scenario: Ask returns a question back
- **WHEN** a peer asks with `ask(to, "weather?")` and the answer is `Reply("which city?", status="asked")`
- **THEN** `ask` returns `which city?`

#### Scenario: Ask raises on an error answer
- **WHEN** a peer asks with `ask(to, "weather?")` and the answer is `Reply("quota exceeded", status="error")`
- **THEN** `ask` raises `PeerError` whose text is `quota exceeded`, and the answer is still in the conversation with status `error`
