# Spec Delta

## Purpose

Turns a headless chatinho session into an MCP server, so MCP clients — including other chatinho sessions — can put questions to it, get exactly one answer per question, and lend their own intelligence to the peers that answer them.

## ADDED Requirements

### Requirement: MCP server as the session's frontend
chatinho SHALL provide `McpServerFrontend` in `chatinho[mcp]`: a `@frontend` that serves the session over MCP in place of a terminal. Its `serve()` MUST run the MCP server until the transport closes, so `session.run()` ends with it. It MUST support the stdio transport and the Streamable HTTP transport; the HTTP transport MUST require a bearer token configured on the frontend and refuse requests without it. Several clients MAY be connected at once.

#### Scenario: Session ends with the server
- **WHEN** a session whose frontend is `McpServerFrontend` on stdio is run and its client closes the connection
- **THEN** `session.run()` returns and every peer is shut down

#### Scenario: HTTP without the token
- **WHEN** an HTTP request reaches the server without the configured bearer token
- **THEN** it is refused and no peer is asked anything

### Requirement: Questions only, to the session
The server SHALL expose these MCP tools and no tool that broadcasts on the client's behalf: `ask(text, asker?, deadline_ms?)`, `list_peers()`, `list_commands()`, `invoke(name, args)` and `read_attachment(msg_id, name)`. `ask` MUST NOT take a peer name: the session decides who answers. `list_peers` MUST return the names of the session's answering peers, excluding the frontend and the asker proxies.

#### Scenario: No broadcast tool
- **WHEN** a client lists the server's tools
- **THEN** there is no tool that says something to everyone, and `ask` has no peer parameter

#### Scenario: Listing peers
- **WHEN** a client calls `list_peers` on a session with peers `agent` and `weather`
- **THEN** the result is `agent` and `weather`, without the frontend or any asker's proxy

### Requirement: The session decides who answers
For each `ask`, the server SHALL count the session's answering peers: peers that declare `HookAnswer`, excluding the frontend and the asker proxies. With exactly one, it MUST ask that peer directly from the asker's proxy. With more than one, it MUST say the question to the room from the asker's proxy and take the first message that replies to it as the answer; later replies stay in the conversation but are not returned. A said question reaches only peers that declare `HookListen`, so when none of the answering peers listens, the result MUST be `error` at once instead of waiting for the deadline. With none, the result MUST be `error`. This rule stands in for a future peer router.

#### Scenario: Only one peer
- **WHEN** a client asks "will it rain?" of a session whose only answering peer is `weather`
- **THEN** `weather` is asked directly, and its answer is the result

#### Scenario: Several peers
- **WHEN** a client asks "draw the login flow" of a session with peers `agent` and `weather`, `agent` listens, and `agent` replies to the question
- **THEN** the question was said to the room, and `agent`'s reply is the result

#### Scenario: None listens
- **WHEN** a client asks a session with peers `agent` and `weather`, neither of which declares `HookListen`
- **THEN** the result is `error` at once, saying that several peers could answer and none listens, so a peer router is needed

#### Scenario: First reply wins
- **WHEN** two peers reply to the same broadcast question
- **THEN** the result is the first reply, and the second one stays in the conversation

#### Scenario: No peer
- **WHEN** a client asks a session with no answering peer
- **THEN** the result is `error` saying no peer can answer

### Requirement: Exactly one result per question
Every `ask` SHALL return exactly one result `{status, text, attachments}`, with `status` one of `answered`, `asked` (answered with a question back to the asker), `error` or `timeout`. It MUST return before the request's deadline: the caller's `deadline_ms`, or else the frontend's default deadline, which is configurable when the frontend is created and is 120 seconds when not set; a question nobody has answered by then MUST yield `timeout`. A failing peer and a failed sample MUST yield `error` with a message saying what failed. Results of `error` and `timeout` MUST be marked as tool errors in MCP. A direct answer carries the status of the peer's `Reply` (`answered` for plain text); a reply to a broadcast question MUST yield `answered`.

#### Scenario: Answered
- **WHEN** the session's only peer `weather` answers `sunny`
- **THEN** the result is `answered` with text `sunny`

#### Scenario: Nobody answers in time
- **WHEN** a client asks with a deadline of 1 second and no answer comes within it
- **THEN** the result is `timeout`, returned within the deadline

#### Scenario: Configured default deadline
- **WHEN** the frontend is created with a default deadline of 30 seconds and a client asks without `deadline_ms`
- **THEN** a question not answered after 30 seconds yields `timeout`

#### Scenario: Answered with a question
- **WHEN** the answering peer returns `Reply("which login flow?", status="asked")`
- **THEN** the result is `asked` with that text

#### Scenario: Follow-up after a question back
- **WHEN** the previous result for an asker was `asked`, and the same asker asks again
- **THEN** with one peer, that peer is asked again from the same proxy; with several, the new question is said as a reply to the `asked` answer, so the peer that asked sees it is for it

### Requirement: One peer per asker
For each distinct asker, the server SHALL add a proxy peer to the session, with its own id, named by the client's name, as given in the MCP handshake, followed by `/` and the asker's name when the client sends one (for example `lab/me`). Questions from that asker MUST be asked or said from its proxy, so peers see them as coming from that name. A proxy asked a question MUST answer `error`. A proxy MUST be removed when its client disconnects; its messages MUST stay in the conversation.

#### Scenario: Asker appears by name
- **WHEN** a client named `lab` sends a question from `me`
- **THEN** the remote peers see it coming from a peer named `lab/me`, which `peers()` lists while `lab` is connected

#### Scenario: Two clients are two askers
- **WHEN** clients `lab` and `home` each ask the same session
- **THEN** the questions come from two different peer ids, `lab/…` and `home/…`

#### Scenario: Proxy leaves on disconnect
- **WHEN** client `lab` disconnects
- **THEN** its proxy peers are removed from the session and their earlier messages remain in the context

### Requirement: Attachments come back with the answer
Attachments of an answer SHALL be returned in the result, each with its name, media type and content, so the asking side can keep them; `read_attachment(msg_id, name)` MUST return an attachment of an earlier answer through the session's backend, or an error when there is none.

#### Scenario: Drawing returned
- **WHEN** the answering peer attaches `chart.svg`
- **THEN** the result carries `chart.svg` with media type `image/svg+xml` and its bytes

### Requirement: Sampling relayed to the asker
The server SHALL serve `HookSample` for the session: a sample requested on behalf of a question from an asker's proxy MUST be relayed as an MCP sampling request to the client that asker came through, and its completion returned to the peer. A sample for a message that came from no client, or a client that declines or does not support sampling, MUST raise `SamplingUnavailable` in the peer. The server MUST NOT accept, store or forward API keys, except credentials delegated as the `credential-delegation` capability allows.

#### Scenario: Peer uses the asker's model
- **WHEN** client `lab` asks, and the answering peer calls `sample` on behalf of that question
- **THEN** `lab` receives a sampling request and the completion it returns is what `sample` returns

#### Scenario: Sampling for a broadcast question
- **WHEN** the question was said to the room and a peer replying to it calls `sample` on behalf of it
- **THEN** the request is relayed to the asker's client, as for a direct question

#### Scenario: No client behind the message
- **WHEN** a peer calls `sample` on behalf of a message said by another local peer
- **THEN** `sample` raises `SamplingUnavailable`
