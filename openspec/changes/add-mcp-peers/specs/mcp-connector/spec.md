# Spec Delta

## Purpose

Lets a chatinho session reach the peers of another session over MCP through one ordinary peer, addressed by name and route, while lending the local model to the remote peers that answer.

## ADDED Requirements

### Requirement: A connector to a remote session
chatinho SHALL provide `McpConnector` in `chatinho[mcp]`: an ordinary `@connector` built from a server to connect to (a command to start over stdio, or an HTTP URL with a bearer token), a `name`, an optional default `peer` and an optional `deadline` (sent with every question it starts; when not set, the server's default applies). Its name in the chat MUST be the `name` given, or the name the server announces when none is given, and MUST be sent to the server as the client name in the MCP handshake.

#### Scenario: Named by the connector
- **WHEN** `McpConnector(url=..., token=..., name="lab")` is added to a session
- **THEN** it appears in the chat as `lab`, and the server sees a client named `lab`

#### Scenario: Default name from the server
- **WHEN** no `name` is given and the server announces itself as `office`
- **THEN** the connector appears as `office`

### Requirement: Addressing remote peers
The connector SHALL reply only to messages addressed to it: a message from the local user starting with `@<name>` (its own name), or a question asked to it directly. After `@<name>`, an optional `/peer` path selects the route (`@lab/weather …`, `@lab/office/weather …`); with no path, the default `peer` is asked, and with no default the connector answers that a peer must be named. The route and the remaining text MUST be sent as one `ask`.

#### Scenario: Addressed by route
- **WHEN** the user says `@lab/office/weather will it rain?`
- **THEN** the connector asks the remote session with route `["office", "weather"]` and text `will it rain?`

#### Scenario: Not addressed
- **WHEN** the user says something that does not start with `@lab`
- **THEN** the connector forwards nothing and says nothing

#### Scenario: Default peer
- **WHEN** the connector's default peer is `agent` and the user says `@lab draw the login flow`
- **THEN** the remote `agent` is asked `draw the login flow`

### Requirement: Every question gets one answer
For every message it is addressed by, the connector SHALL post exactly one reply to it: the remote answer's text, with its attachments attached, when the status is `answered`; the remote peer's question, marked as a question back to the asker, for `asked`; and a short message naming the status and hop for `error` and `timeout`. Losing the connection MUST also produce a reply saying so.

#### Scenario: Answer with an attachment
- **WHEN** the remote answer is `answered` with attachment `chart.svg`
- **THEN** the connector replies with the text and attaches `chart.svg`, so the local backend keeps it

#### Scenario: Answered with a question
- **WHEN** the remote result is `asked` with "which login flow?"
- **THEN** the connector replies with that question, marked as a question from the remote peer, and the user's next `@lab/…` message to the same peer continues that conversation

#### Scenario: Remote error
- **WHEN** the remote result is `error` at hop `office` with "no peer named weather"
- **THEN** the connector replies with a short message naming the hop and the error

#### Scenario: Connection lost
- **WHEN** the server is unreachable while a question is being asked
- **THEN** the connector replies that the remote session could not be reached

### Requirement: The asker's path travels with the question
The connector SHALL send, with each question, the path of who asked it: the local asker's name when the question started in this session, or the asker path it was given when it is forwarding a question for a server, so that the remote side can name the asker by the reverse route.

#### Scenario: Local user asks
- **WHEN** the local user `me` asks through connector `lab`
- **THEN** the remote session sees the asker as `lab/me`

#### Scenario: Forwarded question
- **WHEN** a session's connector `office` forwards a question whose asker is `lab/me`
- **THEN** the next session sees the asker as `office/lab/me`

### Requirement: Serving samples with the local model
The connector SHALL answer MCP sampling requests from its server: for a question that started in this session, with a sample function given to the connector (for example one backed by the local LLM); for a question it is forwarding, by relaying the request through its own session's `sample` on behalf of the message it is answering. With no sample function and nothing to relay to, it MUST decline the request. The connector MUST NOT send any API key to the server.

#### Scenario: Local model answers the remote peer
- **WHEN** the connector was given a sample function and the server sends a sampling request for a question the local user asked
- **THEN** the sample function is called and its completion is returned to the server

#### Scenario: Relayed toward the origin
- **WHEN** the connector is forwarding a question for its own session's server and receives a sampling request
- **THEN** it calls its session's `sample` on behalf of the message it is answering, which relays the request one hop closer to the origin

#### Scenario: Nothing to sample with
- **WHEN** the connector has no sample function and the question started in its own session
- **THEN** the sampling request is declined, and the remote peer gets `SamplingUnavailable`
