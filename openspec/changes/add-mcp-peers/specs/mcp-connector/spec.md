# Spec Delta

## Purpose

Lets a chatinho session put questions to another session over MCP through one ordinary peer, addressed by name, while lending the local model to the remote peers that answer.

## ADDED Requirements

### Requirement: A connector to a remote session
chatinho SHALL provide `McpConnector` in `chatinho[mcp]`: an ordinary `@connector` built from a server to connect to (a command to start over stdio, or an HTTP URL with a bearer token), a `name` and an optional `deadline` (sent with every question it sends; when not set, the server's default applies). It MUST speak the modern MCP protocol (2026-07-28). Its name in the chat MUST be the `name` given, or the server's name when none is given, and MUST be sent to the server as the client name with every request.

#### Scenario: Named by the connector
- **WHEN** `McpConnector(url=..., token=..., name="lab")` is added to a session
- **THEN** it appears in the chat as `lab`, and the server sees requests from a client named `lab`

#### Scenario: Default name from the server
- **WHEN** no `name` is given and the server's frontend is named `office`
- **THEN** the connector appears as `office`

### Requirement: Addressing the remote session
The connector SHALL send a question only for messages addressed to it: a message starting with `@<name>` (its own name) followed by whitespace, or a question asked to it directly. The rest of the text MUST be sent as one `ask` to the remote session, without naming a remote peer; the remote session decides who answers.

#### Scenario: Addressed by name
- **WHEN** the user says `@lab will it rain?`
- **THEN** the connector asks the remote session `will it rain?`

#### Scenario: Not addressed
- **WHEN** the user says something that does not start with `@lab`
- **THEN** the connector sends nothing and says nothing

### Requirement: Every question gets one answer
For every message it is addressed by, the connector SHALL post exactly one reply to it: the remote answer's text, with its attachments attached, when the status is `answered`; the remote peer's question, marked as a question back to the asker, for `asked`; and a short message naming the status for `error` and `timeout`. Losing the connection MUST also produce a reply saying so.

#### Scenario: Answer with an attachment
- **WHEN** the remote answer is `answered` with attachment `chart.svg`
- **THEN** the connector replies with the text and attaches `chart.svg`, so the local backend keeps it

#### Scenario: Answered with a question
- **WHEN** the remote result is `asked` with "which login flow?"
- **THEN** the connector replies with that question, marked as a question from the remote session, and the user's next `@lab …` message continues that conversation

#### Scenario: Remote error
- **WHEN** the remote result is `error` with "no peer can answer"
- **THEN** the connector replies with a short message saying so

#### Scenario: Connection lost
- **WHEN** the server is unreachable while a question is being asked
- **THEN** the connector replies that the remote session could not be reached

### Requirement: The asker travels with the question
The connector SHALL send, with each question, the name of the local peer that asked it, so the remote session can show the asker as `<connector name>/<asker>`.

#### Scenario: Local user asks
- **WHEN** the local user `me` asks through connector `lab`
- **THEN** the remote session sees the asker as `lab/me`

### Requirement: Serving samples with the local model
The connector SHALL answer the sampling requests its server embeds in an `InputRequiredResult` with a sample function given to the connector (for example one backed by the local LLM), and retry the question with the completions, for as many rounds as the question needs within its deadline. With no sample function, it MUST decline the request. The connector MUST NOT send any API key to the server, except credentials it is configured to delegate (see `credential-delegation`).

#### Scenario: Local model answers the remote peer
- **WHEN** the connector was given a sample function and the server sends a sampling request for a question the local user asked
- **THEN** the sample function is called and its completion is returned to the server

#### Scenario: Nothing to sample with
- **WHEN** the connector has no sample function
- **THEN** the sampling request is declined, and the remote peer gets `SamplingUnavailable`
