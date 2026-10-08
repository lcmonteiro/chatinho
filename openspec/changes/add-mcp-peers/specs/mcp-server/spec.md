# Spec Delta

## Purpose

Turns a headless chatinho session into an MCP server, so MCP clients — including other chatinho sessions — can put questions to it, get exactly one answer per question, and lend credentials with each message to the peers that answer it.

## ADDED Requirements

### Requirement: MCP server as the session's frontend
chatinho SHALL provide `McpFrontend` in `chatinho[mcp]`: a `@frontend` that serves the session over the modern MCP protocol (2026-07-28) in place of a terminal. Its name in the session, which it also gives as the server's name, MUST be `master` unless another name is given. Its `serve()` MUST run the MCP server over Streamable HTTP until it stops, so `session.run()` ends with it. There is no stdio transport. The frontend MUST be created with a bearer token, and MUST refuse every request without it. Several clients MAY use it at once; each request names its client.

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
The server SHALL expose the MCP tools `say`, `ask`, `peers`, `tools` and `run`: what a person at the terminal can do. `say(text, asker?, deadline_ms?)` works as a bridge: the frontend says the text in the session as its own message and returns the first reply to it; it MUST NOT take a peer name, so the session decides who replies. Any other tool name MUST yield `error`.

#### Scenario: The tools
- **WHEN** a client lists the server's tools
- **THEN** they are `say`, `ask`, `peers`, `tools` and `run`, and `say` has no peer parameter

### Requirement: Asking one peer
`ask(peer, text, deadline_ms?)` SHALL say the text in the session addressed to the peer of that name, so it is asked of that peer, and return its answer under the same one-result rule as `say`, with the same deadline and lent credentials. When no peer other than the frontend has that name, several do, or the peer does not declare `HookAnswer`, the result MUST be `error` at once.

#### Scenario: Asked by name
- **WHEN** a client asks `weather` "rain?" in a session with peers `agent` and `weather`
- **THEN** only `weather` is asked, and its answer is the result

#### Scenario: Nobody by that name
- **WHEN** a client asks a peer name that is not in the session
- **THEN** the result is `error` saying no peer has that name

### Requirement: The roster and the tools
`peers()` SHALL list every peer but the frontend, each with its name and whether it answers. `tools()` SHALL list the session's commands, each with its name and description. `run(name, args?, deadline_ms?)` SHALL run the named command, with or without a leading `/`, and return what it answered as `answered`; an unknown command MUST yield `error`, and a command still running at the deadline MUST yield `timeout`.

#### Scenario: Listing peers
- **WHEN** a client calls `peers` in a session with `agent` and a peer `mute` that does not answer
- **THEN** the result lists `agent` as answering and `mute` as not

#### Scenario: Running a tool
- **WHEN** a client runs `eco` with `hi` and the command answers `eco: hi`
- **THEN** the result is `answered` with text `eco: hi`

### Requirement: The session decides who replies
For each `say`, the frontend SHALL count the session's answering peers: peers that declare `HookAnswer`, excluding the frontend. With exactly one, the session asks it the say (see `answer-details`). With more than one, the say goes to the room and the first message that replies to it is the result; later replies stay in the conversation but are not returned. A said message reaches only peers that declare `HookListen`, so when several peers answer and none of them listens, the result MUST be `error` at once instead of waiting for the deadline. With none, the result MUST be `error`. This rule stands in for a future peer router.

#### Scenario: Only one peer
- **WHEN** a client says "will it rain?" to a session whose only answering peer is `weather`
- **THEN** `weather` is asked it, and its answer is the result

#### Scenario: Several peers
- **WHEN** a client says "draw the login flow" to a session with peers `agent` and `weather`, `agent` listens, and `agent` replies to it
- **THEN** it was said to the room, and `agent`'s reply is the result

#### Scenario: None listens
- **WHEN** a client says something to a session with peers `agent` and `weather`, neither of which declares `HookListen`
- **THEN** the result is `error` at once, saying that several peers could answer and none listens, so a peer router is needed

#### Scenario: First reply wins
- **WHEN** two peers reply to the same message in the room
- **THEN** the result is the first reply, and the second one stays in the conversation

#### Scenario: No peer
- **WHEN** a client says something to a session with no answering peer
- **THEN** the result is `error` saying no peer can answer

### Requirement: Exactly one result per question
Every `say` SHALL return exactly one result `{status, text, attachments, msg_id}`, where `msg_id` is the reply's message id and is absent when no reply arrived, with `status` one of `answered`, `asked` (answered with a question back to the asker), `error` or `timeout`. It MUST return before the request's deadline: the caller's `deadline_ms`, or else the frontend's default deadline, which is configurable when the frontend is created and is 120 seconds when not set; a question nobody has answered by then MUST yield `timeout`. A failing peer MUST yield `error` with a message saying what failed. Results of `error` and `timeout` MUST be marked as tool errors in MCP. The result carries the status of the reply's message: the peer's `Reply` status when the lone peer was asked, `answered` for a plain text or a reply said in the room.

#### Scenario: Answered
- **WHEN** the session's only peer `weather` answers `sunny`
- **THEN** the result is `answered` with text `sunny`

#### Scenario: Nobody answers in time
- **WHEN** a client says something with a deadline of 1 second and no reply comes within it
- **THEN** the result is `timeout`, returned within the deadline

#### Scenario: Configured default deadline
- **WHEN** the frontend is created with a default deadline of 30 seconds and a client says something without `deadline_ms`
- **THEN** a question not answered after 30 seconds yields `timeout`

#### Scenario: Answered with a question
- **WHEN** the answering peer returns `Reply("which login flow?", status="asked")`
- **THEN** the result is `asked` with that text

#### Scenario: Follow-up from the same asker
- **WHEN** an asker got an answer, for example a question back, and asks again
- **THEN** with one peer, that peer is asked again; with several, the new question is said as a reply to the asker's last answer in the room (a reply there always reads `answered`, so a question back cannot be told apart), and the peer that answered sees it is for it

### Requirement: The frontend speaks for every client
The frontend SHALL handle every client itself, without adding a peer per client: for each message it receives, it MUST say the text in the session as its own message, remember which client's message that is, and send the reply to that message back to that client alone. Questions from several clients MAY be open at once, and each reply MUST reach only the client whose question it answers. A peer that asks the frontend a question MUST get `error`, since nobody is at its terminal.

#### Scenario: The reply goes back to its client
- **WHEN** a client says "will it rain?" and the session's only peer answers "sunny"
- **THEN** the peer was asked it by the frontend, and that client's result is "sunny"

#### Scenario: Two clients at once
- **WHEN** clients `lab` and `home` each say something while the other's message still waits
- **THEN** each gets the reply to its own message, and no peer was added to the session

#### Scenario: Asking the frontend
- **WHEN** a peer asks the frontend a question
- **THEN** it gets an `error` reply saying nobody is at the terminal

### Requirement: Attachments come back with the answer
Attachments of an answer SHALL be returned in the result, each with its name, media type and content, so the asking side can keep them.

#### Scenario: Drawing returned
- **WHEN** the answering peer attaches `chart.svg`
- **THEN** the result carries `chart.svg` with media type `image/svg+xml` and its bytes

### Requirement: No key held by default
The server MUST NOT accept, store or forward API keys, except credentials delegated as the `credential-delegation` capability allows.

#### Scenario: A client lends nothing
- **WHEN** a client says something without delegating a credential
- **THEN** no peer can obtain one for that message
