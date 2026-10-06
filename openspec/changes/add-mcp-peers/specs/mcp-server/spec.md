# Spec Delta

## Purpose

Turns a headless chatinho session into an MCP server, so MCP clients — including other chatinho sessions — can ask its peers directly, get exactly one answer per question, and lend their own intelligence to the peers that answer them.

## ADDED Requirements

### Requirement: MCP server as the session's frontend
chatinho SHALL provide `McpServerFrontend` in `chatinho[mcp]`: a `@frontend` that serves the session over MCP in place of a terminal. Its `serve()` MUST run the MCP server until the transport closes, so `session.run()` ends with it. It MUST support the stdio transport and the Streamable HTTP transport; the HTTP transport MUST require a bearer token configured on the frontend and refuse requests without it. Several clients MAY be connected at once.

#### Scenario: Session ends with the server
- **WHEN** a session whose frontend is `McpServerFrontend` on stdio is run and its client closes the connection
- **THEN** `session.run()` returns and every peer is shut down

#### Scenario: HTTP without the token
- **WHEN** an HTTP request reaches the server without the configured bearer token
- **THEN** it is refused and no peer is asked anything

### Requirement: Directed questions only
The server SHALL expose these MCP tools and no tool that broadcasts: `ask(route, text, deadline_ms?)`, `list_peers()`, `list_commands()`, `invoke(name, args)` and `read_attachment(msg_id, name)`. `route` is a non-empty list of peer names; `list_peers` MUST return the names of the session's peers, excluding the frontend and the proxies of other askers.

#### Scenario: No broadcast
- **WHEN** a client lists the server's tools
- **THEN** there is no tool that says something to everyone

#### Scenario: Listing peers
- **WHEN** a client calls `list_peers` on a session with peers `agent` and `weather`
- **THEN** the result is `agent` and `weather`, without the frontend or any asker's proxy

### Requirement: Exactly one result per question
Every `ask` SHALL return exactly one result `{status, text, attachments, hop}`, with `status` one of `answered`, `asked` (answered with a question back to the asker), `error` or `timeout`, and `hop` the route of the session that produced it. It MUST return before the request's deadline: the caller's `deadline_ms`, or else the frontend's default deadline, which is configurable when the frontend is created and is 120 seconds when not set; a peer that has not answered by then MUST yield `timeout`. An unknown peer name, a failing peer and a failed sample MUST yield `error` with a message saying what failed. Results of `error` and `timeout` MUST be marked as tool errors in MCP. A peer's plain text answer MUST yield `answered`; a peer MAY instead return `asked` or `error` explicitly.

#### Scenario: Answered
- **WHEN** a client asks `weather` and it answers `sunny`
- **THEN** the result is `answered` with text `sunny`

#### Scenario: Unknown peer
- **WHEN** a client asks `wether`, which is not a peer
- **THEN** the result is `error` saying there is no peer named `wether`

#### Scenario: Peer does not answer in time
- **WHEN** a client asks with a deadline of 1 second and the peer does not answer within it
- **THEN** the result is `timeout`, returned within the deadline

#### Scenario: Answered with a question
- **WHEN** the peer answers with an explicit `asked` status: "which login flow?"
- **THEN** the result is `asked` with that text, and a following `ask` from the same asker to the same peer continues the same conversation

#### Scenario: Configured default deadline
- **WHEN** the frontend is created with a default deadline of 30 seconds and a client asks without `deadline_ms`
- **THEN** a peer that has not answered after 30 seconds yields `timeout`

### Requirement: One peer per asker
For each distinct asker, the server SHALL add a proxy peer to the session, with its own id, named by the asker's reverse route: the client's name, as given in the MCP handshake, followed by `/` and the asker's own path when the client relays one (for example `lab/me`). Questions from that asker MUST be asked from its proxy, so peers see them as coming from that name. A proxy MUST be removed when its client disconnects; its messages MUST stay in the conversation.

#### Scenario: Asker appears by name
- **WHEN** a client named `lab` relays a question from `me`
- **THEN** the remote peer is asked by a peer named `lab/me`, which `peers()` lists while `lab` is connected

#### Scenario: Two clients are two askers
- **WHEN** clients `lab` and `home` each ask the same peer
- **THEN** the questions come from two different peer ids, `lab/…` and `home/…`

#### Scenario: Proxy leaves on disconnect
- **WHEN** client `lab` disconnects
- **THEN** its proxy peers are removed from the session and their earlier messages remain in the context

### Requirement: Routes across sessions
When `route` has more than one name, the server SHALL ask its first element, which MUST be a peer able to forward (an `McpConnector`), passing it the rest of the route, the remaining time before the deadline, and the visited-session list. Each request MUST carry a list of visited session ids, random per session; a server that finds its own id in the list, or a route longer than the hop limit (default 8), MUST answer `error` without asking anyone. Results from further hops MUST be returned unchanged except for `hop`, which names where they were produced.

#### Scenario: Two hops
- **WHEN** a client asks route `["office", "weather"]` and `office` is a connector to a session with peer `weather`
- **THEN** the result is `weather`'s answer, with `hop` naming `office/weather`

#### Scenario: Loop refused
- **WHEN** a request arrives whose visited list already contains this session's id
- **THEN** the result is `error` reporting a loop, and no peer is asked

#### Scenario: Error names the hop
- **WHEN** the session behind `office` has no peer `weather`
- **THEN** the result is `error` with `hop` naming `office` and a message saying there is no peer `weather`

### Requirement: Attachments come back with the answer
Attachments of an answer SHALL be returned in the result, each with its name, media type and content, so the asking side can keep them; `read_attachment(msg_id, name)` MUST return an attachment of an earlier answer through the session's backend, or an error when there is none.

#### Scenario: Drawing returned
- **WHEN** the answering peer attaches `chart.svg`
- **THEN** the result carries `chart.svg` with media type `image/svg+xml` and its bytes

### Requirement: Sampling relayed to the asker
The server SHALL serve `HookSample` for the session: a sample requested on behalf of a message from an asker's proxy MUST be relayed as an MCP sampling request to the client that asker came through, and its completion returned to the peer. A sample for a message that came from no client, or a client that declines or does not support sampling, MUST raise `SamplingUnavailable` in the peer. The server MUST NOT accept, store or forward API keys.

#### Scenario: Peer uses the asker's model
- **WHEN** client `lab` asks `agent`, and `agent` calls `sample` on behalf of that question
- **THEN** `lab` receives a sampling request and the completion it returns is what `sample` returns

#### Scenario: No client behind the message
- **WHEN** a peer calls `sample` on behalf of a message said by another local peer
- **THEN** `sample` raises `SamplingUnavailable`
