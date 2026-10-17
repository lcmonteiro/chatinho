## MODIFIED Requirements

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
