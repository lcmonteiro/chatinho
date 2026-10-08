# Spec Delta

## Purpose

Lets a chatinho session put questions to another session over MCP through one ordinary peer that is asked, while lending credentials, with each question, to the remote peers that answer.

## ADDED Requirements

### Requirement: A connector to a remote session
chatinho SHALL provide `McpConnector` in `chatinho[mcp]`: an ordinary `@connector` built from a server to connect to (an HTTP URL with a bearer token, or an in-process server), and a `name`. It MUST speak the modern MCP protocol (2026-07-28). Its name in the chat MUST be the `name` given, or the server's name when none is given, and MUST be sent to the server as the client name with every request.

#### Scenario: Named by the connector
- **WHEN** `McpConnector(url=..., token=..., name="lab")` is added to a session
- **THEN** it appears in the chat as `lab`, and the server sees requests from a client named `lab`

#### Scenario: Default name from the server
- **WHEN** no `name` is given and the server's frontend is named `office`
- **THEN** the connector appears as `office`

### Requirement: Asking the remote session
The connector SHALL send a question only when it is asked (`HookAnswer`); it MUST NOT listen to what is said in the room. A leading `@<name>` (its own name) followed by whitespace MAY prefix the question and is dropped. The text MUST be sent as one `say` to the remote session, without naming a remote peer; the remote session decides who answers.

#### Scenario: Asked directly
- **WHEN** a peer asks the connector `@lab will it rain?`
- **THEN** the connector asks the remote session `will it rain?`

#### Scenario: Said to the room
- **WHEN** the user says `@lab will it rain?` in a local chat where another peer also answers
- **THEN** the connector sends nothing and says nothing

#### Scenario: The only answering peer here
- **WHEN** the connector is the only peer in the local chat that answers, and the user says `will it rain?` without `@lab`
- **THEN** the session asks the connector, by the core rule, and the connector asks the remote session `will it rain?`

### Requirement: Every question gets one answer
For every question it is asked, the connector SHALL answer exactly once: the remote answer's text, with its attachments attached, when the status is `answered`; the remote peer's question, marked as a question back to the asker, for `asked`; and a short error naming the remote session for a tool error. Losing the connection MUST also produce a reply saying so.

#### Scenario: Answer with an attachment
- **WHEN** the remote answer is `answered` with attachment `chart.svg`
- **THEN** the connector replies with the text and attaches `chart.svg`, so the local backend keeps it

#### Scenario: Answered with a question
- **WHEN** the remote result is `asked` with "which login flow?"
- **THEN** the connector replies with that question, marked as a question from the remote session, and the next question asked of it continues that conversation

#### Scenario: Remote error
- **WHEN** the remote result is `error` with "no peer can answer"
- **THEN** the connector replies with a short message saying so

#### Scenario: Connection lost
- **WHEN** the server is unreachable while a question is being asked
- **THEN** the connector replies that the remote session could not be reached

### Requirement: The asker travels with the question
The connector SHALL send, with each question, the name of the local peer that asked it, so the remote frontend can keep each asker's follow-ups together.

#### Scenario: Local user asks
- **WHEN** the local user `me` asks through connector `lab`
- **THEN** the question reaches the remote frontend from client `lab` with asker `me`

### Requirement: No key leaves without delegation
The connector MUST NOT send any API key or credential to the server, except the credentials it is configured to delegate (see `credential-delegation`).

#### Scenario: Nothing configured
- **WHEN** a connector without `delegate` asks a server that declared credentials
- **THEN** the request carries no credential
