## ADDED Requirements

### Requirement: Its client closes with the chat
The OpenAI connector SHALL close the client it keeps for its own key when the chat closes. A connector that never built a client MUST close without error.

#### Scenario: Asked, then closed
- **WHEN** an OpenAI connector answers a question with its own key, and the chat is closed
- **THEN** the client it built for that key is closed

#### Scenario: Never asked
- **WHEN** an OpenAI connector is never asked anything, and the chat is closed
- **THEN** closing raises nothing
