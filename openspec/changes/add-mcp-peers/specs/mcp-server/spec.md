# Spec Delta

## Purpose

Turns a headless chatinho session into an MCP server, so MCP clients — including other chatinho sessions — can put questions to it, get exactly one answer per question, and lend credentials with each message to the peers that answer it.

## ADDED Requirements

### Requirement: MCP server as the session's frontend
chatinho SHALL provide `McpFrontend` in `chatinho[mcp]`: a `@frontend` that serves the session over the modern MCP protocol (2026-07-28) in place of a terminal. Its name in the session, which it also gives as the server's name, MUST be `master` unless another name is given. Its `serve()` MUST run the MCP server over Streamable HTTP until it stops, so `session.run()` ends with it. There is no stdio transport. The frontend MUST be created with a bearer token, and MUST refuse every request without it. Several clients MAY use it at once.

#### Scenario: Named master by default
- **WHEN** a session is created with `McpFrontend(token=…)` and no name
- **THEN** the frontend appears in the session as `master`, and clients see a server named `master`

#### Scenario: No token, no frontend
- **WHEN** code creates an `McpFrontend` without a token
- **THEN** it is refused

#### Scenario: HTTP without the token
- **WHEN** an HTTP request reaches the server without the configured bearer token
- **THEN** it is refused and no peer is asked anything

### Requirement: The terminal's tools
The server SHALL expose exactly the MCP tools `ask`, `peers`, `tools` and `invoke`: what a person at the terminal can do. There is no `say` tool: a client always names the peer it asks. Any other tool name MUST yield a tool error.

#### Scenario: The tools
- **WHEN** a client lists the server's tools
- **THEN** they are `ask`, `peers`, `tools` and `invoke`

### Requirement: Asking one peer
`ask(peer, text)` SHALL say the text in the session addressed to the peer of that name, so the session asks it of that peer, and return that peer's answer. When no peer other than the frontend has that name, several do, or the peer does not declare `HookAnswer`, the result MUST be a tool error at once.

#### Scenario: Asked by name
- **WHEN** a client asks `weather` "rain?" in a session with peers `agent` and `weather`
- **THEN** only `weather` is asked, and its answer is the result

#### Scenario: Nobody by that name
- **WHEN** a client asks a peer name that is not in the session
- **THEN** the result is a tool error saying no peer has that name

### Requirement: The roster and the tools
`peers()` SHALL list every peer but the frontend, each with its name and whether it answers. `tools()` SHALL list the session's commands, each with its name and description. `invoke(name, args?)` SHALL invoke the named command, with or without a leading `/`, and return what it answered as `answered`; an unknown or failing command MUST yield a tool error.

#### Scenario: Listing peers
- **WHEN** a client calls `peers` in a session with `agent` and a peer `mute` that does not answer
- **THEN** the result lists `agent` as answering and `mute` as not

#### Scenario: Invoking a tool
- **WHEN** a client invokes `eco` with `hi` and the command answers `eco: hi`
- **THEN** the result is `answered` with text `eco: hi`

### Requirement: Exactly one result per question
Every `ask` SHALL end in exactly one result: an answer `{status, text, attachments, msg_id}`, where `msg_id` is the reply's message id and `status` is the reply's own, `answered` or `asked` (answered with a question back to the asker), or a tool error. There is no deadline: the call waits for the reply, and a client that ends its call MUST leave nothing of the question waiting. A failing peer, or a reply whose status is `error`, MUST yield a tool error with a message saying what failed.

#### Scenario: Answered
- **WHEN** a client asks `weather` and it answers `sunny`
- **THEN** the result is `answered` with text `sunny`

#### Scenario: Answered with a question
- **WHEN** the asked peer returns `Reply("which login flow?", status="asked")`
- **THEN** the result is `asked` with that text, and the client's next `ask` of that peer continues the conversation

#### Scenario: The client gives up
- **WHEN** a client ends its `ask` call before any reply comes
- **THEN** the frontend stops waiting for that question and lets go of what it held

### Requirement: The frontend speaks for every client
The frontend SHALL handle every client itself, without adding a peer per client: for each question it receives, it MUST say the text in the session as its own message, addressed to the asked peer, remember which call it belongs to, and send the reply to that message back on that call alone. Questions from several clients MAY be open at once, and each reply MUST reach only the call whose question it answers. The frontend MUST NOT declare `HookAnswer`: nobody is at its terminal, so no peer can ask it.

#### Scenario: Two clients at once
- **WHEN** clients `lab` and `home` each ask something while the other's question still waits
- **THEN** each gets the reply to its own question, and no peer was added to the session

#### Scenario: The frontend is never asked
- **WHEN** the session counts the peers that answer
- **THEN** the frontend is not one of them

### Requirement: Attachments come back with the answer
Attachments of an answer SHALL be returned in the result, each with its name, media type and content, so the asking side can keep them.

#### Scenario: Drawing returned
- **WHEN** the answering peer attaches `chart.svg`
- **THEN** the result carries `chart.svg` with media type `image/svg+xml` and its bytes

### Requirement: No key held by default
The server MUST NOT accept, store or forward API keys, except credentials delegated as the `credential-delegation` capability allows.

#### Scenario: A client lends nothing
- **WHEN** a client asks something without delegating a credential
- **THEN** no peer can obtain one for that message
