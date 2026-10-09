# Design

## Context

See proposal.md for why. What the code has today, and what shapes the approach:

- A frontend is a peer at `LOCAL` declared with `@frontend`; `ChatApp` gets every capability through grants (`say`, `ask`, `context`, `peers`, `commands`, `invoke`, `locate`). `session.run()` runs every peer's `serve()` and closes when the first one returns, calling `shutdown()` on each peer.
- `ask` returns the answer's text only. `@require(HookAsk, timeout=…)` is documented but not enforced anywhere.
- Attachments go to the backend that declares `HookKeep`, under the message id; anyone with `locate` can get a link to them. With no keeping backend they are dropped.
- A `say` is a broadcast, and a reply to it is another `say` with `reply_to`. Nothing is owed back, so nothing resolves for the sayer; a peer that declares `HookListen` hears every message, including those replies.
- The core is standard library only; batteries are lazy names behind extras, and `tests/test_architecture.py` checks that (and that `docs/SPEC.md` documents every hook).
- FastMCP (4.0), built on the official `mcp` SDK (2.3), speaks two protocol eras. The handshake era (2025-11-25) has `initialize`, a session per connection and server-to-client requests. The modern era (2026-07-28), which this change targets, is stateless:
  - `server/discover` replaces the handshake.
  - Every request carries the client's info and capabilities in `_meta` (`io.modelcontextprotocol/clientInfo`, `…/clientCapabilities`).
  - FastMCP's `Client` can also connect to a `FastMCP` server in-process, which the tests use.
  - FastMCP registers async functions as tools, deriving their schema from the signature, gives a tool the request's `_meta` through its `Context`, declares SEP-2133 extensions with `ServerExtension`, and checks bearer tokens with a `TokenVerifier`.
- Sampling (a server asking its client for a completion) is deprecated in 2026-07-28 (SEP-2577). This change does not use it.

## Goals / Non-Goals

**Goals:**
- One peer in the local chat puts a question to a remote session, and always gets one answer back.
- A remote peer's LLM calls are paid by the session that asked. Paying for them is done by delegating a credential, opt-in and bounded to one question.
- Every piece is testable offline, with FastMCP's in-process client.

**Non-Goals:**
- Routes through several sessions (multi-hop).
- A peer router. Until there is one, the client names the remote peer it asks; `McpConnector` asks the only answering remote peer unless it is given `peer=`.
- Notifications and resource subscriptions.
- Remote peers mirrored one-to-one in the local roster.
- Remote peers asking the remote asker a question (MCP elicitation); the frontend does not answer questions. A remote peer that needs more information answers with status `asked` instead, and the asker's next question continues the conversation.

## Decisions

### 1. Core additions stay small and generic
- **`answer` returns a `Reply`.** Like a command's `execute`, a peer's `answer` returns `Reply | None`; a plain string is a `TypeError`, so every answer carries its status and attachments the same way.
- **`Reply.status`**, a `ReplyStatus` `str` enum (`ANSWERED` | `ASKED` | `ERROR`, default `ANSWERED`; "I don't know" is an `answered` text), carried on the answer's **`ChatMessage.status`**. Whoever hears or reads the reply sees what it said about itself; `ask` still returns the text. The archive does not keep the status.
- **A say in a room with one peer that answers is asked of it.** `say` addresses the message to that peer when it is not a reply, is not from a command, and exactly one peer other than the speaker and the frontend declares `HookAnswer`. Its `answer` is called, and the reply comes back with `reply_to` set to the say. Listeners still hear both. This makes a room with one agent a conversation with it, and it is what lets the MCP bridge use one verb.
- *Alternative, the earlier draft: `ask(..., detail=True) -> Answer(text, status, msg_id)`.* It gave the frontend the status and the answer's id, but only for its own asks. With the status on the message and a say that asks the lone peer, the frontend just says and listens, and `detail` goes.
- **Credentials on the message:** `ChatMessage.credentials`, set through `say(..., credentials=…)` (decision 5).
- *Alternative: MCP sampling, relaying each completion back to the asker.* It was in an earlier draft. It is dropped: it is deprecated in the modern protocol, it costs a round trip per completion, and credential delegation covers the same need.
- **A failing `answer` is a reply.** Today a peer that raises in `answer` leaves its asker waiting forever. The session now sets the exception on a waiting ask, and when nobody awaits the message (a say asked of the lone peer) it posts an `error` reply to it, so the bridge ends in `error` at once.
- **No peer per client.** The frontend listens and resolves its own waits (decisions 3 and 4), and adds or removes no peer.

### 2. Wire format: the terminal's tools
`McpFrontend` builds a `FastMCP` server and registers its own async methods as the tools (`mcp.tool(self._ask, name="ask")`, one line each): FastMCP derives each schema from the signature and each description from the docstring, and a tool reads the request's `_meta` (lent credentials) through its `Context`.
- **Tools:** `ask`, `peers`, `tools` and `invoke`, what a person at the terminal can do, mirroring `ChatApp`'s grants. There is no `say` tool: a client always names the peer it asks. There is no tool to read attachments later; attachments come back with the reply.
  - `ask(peer, text)`: the frontend says the text addressed to the peer of that name (`say(..., to=)`), so it is asked of that peer, and returns its answer. An unknown name, a name several peers share, the frontend's own name, or a peer that does not declare `HookAnswer` is `error` at once.
  - `peers()`: every peer but the frontend, as a typed list of `PeerInfo(name, answers)`; a FastMCP client reads it back as objects from `result.data`.
  - `tools()`: the session's commands, as a typed list of `ToolInfo(name, description)`.
  - `invoke(name, args?)`: runs a command, named as `tools` lists it (no `/`), through the `invoke` grant and returns its answer as `answered`; an unknown or failing command is `error`.
- **Result:** `ask` and `invoke` return an `Answer` model, `{status, text, attachments: [{name, media_type, data_b64}], msg_id}`, with `status` `answered` or `asked` and `msg_id` the reply's message id in the remote session; FastMCP sends it as structured content and as JSON text. A failure, including a reply whose status is `error`, raises `ToolError` with the message, so it is a tool error (`isError`) carrying only that text.
- **Read back:** `McpConnector` turns the result straight into its local `Reply`: a tool error becomes `ReplyStatus.ERROR` naming the remote session, `asked` becomes `ReplyStatus.ASKED`, and anything else is `answered` with its text and attachments.
- **Shared code:** the credentials key and the attachment encoding live in `chatinho/helpers/mcp.py`, standard library only, so each end imports them without the other.
- *Alternative, the earlier draft: the SDK's low-level `Server` (`on_list_tools`, `on_call_tool`).* It gave full control, but the tool schemas, the dispatch by name, the extension and the bearer check were all hand-written; FastMCP gives the same request context with far less code.

### 3. The frontend speaks for every client
The frontend is the session's peer zero, as a terminal is, and it handles every client itself.
- **Receive:** an `ask` tool call arrives, with the peer's name, the text and, in `_meta`, any lent credentials.
- **Forward:** the frontend says the text in the session as its own message, addressed to that peer (`say(text, to=peer)`), so the session asks it of that peer without anyone waiting on a core `ask`.
- **Route back:** it maps that message's id to the open call. Its `listen` resolves the call with the message whose `reply_to` is that id. There is no deadline: the call waits for that reply, and a client that stops waiting ends its call, which lets go of the question.
- **Several clients:** their questions wait at once, each under its own message id.
- **Follow-ups:** a peer that answered `asked` is asked again by the client's next `ask`; it has the conversation's history.
- **Asking the frontend:** it does not declare `HookAnswer`, since nobody is at its terminal; the ask/answer pair is not supported. An answer that arrives after its question ended is only heard.
- *Alternative, the earlier draft: one proxy peer per asker, named `<client>/<asker>`.* It let remote peers tell askers apart, but it needed peers added and removed at run time (`remove_connector`, idle expiry). It is dropped: the frontend manages the connections, and the core stays as it is.

### 4. One result per question
| Outcome | Result |
|---|---|
| The reply arrived, `answered` or `asked` | an `Answer` with the reply's status |
| The reply's status is `error` (for example, the peer raised) | a tool error with its text |
| No peer by that name, several, or one that does not answer | a tool error at once |

- *Alternative, the earlier draft: a `say` tool that said the text to the room and returned the first reply, with the lone-peer rule and follow-ups kept per asker.* It let the remote side choose, but the first reply could come from any peer, and it needed per-asker state. It is dropped: the client names the peer, until a peer router chooses for it.

### 5. Credential delegation (opt-in)
This follows A2A's principle: credentials travel out of band, the server declares what it needs, and a short-lived, scoped credential is preferred to a master key.
- **Core:** the credentials ride on the message as metadata, `ChatMessage.credentials` (keys by name, each a `Secret`), set by `say(..., credentials=…)`. The peer that answers a message reads them from that message, so the key it uses belongs to the message, and one peer can work with a different key for each message.
- *Alternative, the earlier draft: a `HookCredential` grant served by the frontend (`credential(msg_id, name)`).* It worked, but it was a second path to what the message itself can carry.
- **Declaration:** `McpFrontend(credentials={"llm": "OpenAI-compatible API key"})` announces the names in its `server/discover` result, as the capability extension `chatinho/credentials` (SEP-2133 `capabilities.extensions`). Undeclared names are dropped on arrival.
- **Delivery:** `McpConnector(delegate={"llm": value | callable})` discovers the server first, then puts the declared credentials in the `ask` request's `_meta["chatinho/credentials"]`. A callable is called per question, so it can mint short-lived tokens. The connector does not check the transport: serving and reaching the session over HTTPS is the responsibility of whoever builds the system.
- **Lifetime:** the frontend builds the mapping of `Secret`s from the request, says the question with it, and clears that same mapping when the `ask` call ends, so it is gone on every outcome, including a client that gives up and ends its call. The text, the store and logs never hold it, and `ChatMessage`'s `repr` leaves it out.
- **Not passed on:** the credential reaches only the session the connector connects to. A peer that found it on a message must not delegate it further; a connector only delegates its own `delegate` configuration.
- **Using it:** a peer (for example orbe's agent) reads `msg.credentials.get("llm")` and builds its model with that key for this message only; without one, it answers without a model or with its own.
- *Alternative: put the key in the question text or a session-wide setting.* That leaks into history and outlives the question.

### 6. Attachments
- With the reply's message id, the frontend reads each attachment through `locate` (the backend's `file://` link) and returns its bytes base64-encoded.
- The names are the relative link targets in the answer's text. In chatinho a message links its attachments by name, and backends have no way to list a message's attachments. Each name is `locate`d, and names that resolve to nothing are skipped. A session without a linking backend returns no attachments, and the text says so.
- On the asking side, `McpConnector` turns them back into `Attachment`s on its reply, so the local backend keeps them.
- *Alternative: a new grant to fetch attachment bytes.* That's cleaner, but it widens the core more than this change needs. It's noted as follow-up.

### 7. Asking in the local chat
- **Asked only:** `McpConnector` declares `HookAnswer` and nothing that hears the room: it reacts only when it is asked — directly, or by the core rule when it is the only answering peer — and sends the question's text as it is.
- **`@name` in the terminal:** `ChatApp` turns a line `@<name> text` into `say(text, to=peer)`, an ask that nothing waits on, so the input stays free; `@<name>` never reaches the message, and any other line is said as typed.
- *Alternative, the earlier draft: listening for `@<name>` in the room.* It duplicated the session's own routing and needed `HookListen` and `HookSay`; it is dropped.
- **Which remote peer:** the connector asks its `peer`, or, when none was given, the only remote peer that answers, found with the remote `peers` tool. With none or several, it answers with an error asking for `peer=`.

### 8. Connection lifecycle
- `McpConnector` holds one `fastmcp.Client` and opens it per question (`async with client: await client.call_tool("ask", …)`); the protocol is stateless, so no link stays open between questions and there is nothing to close at `shutdown()`. `initialize()` opens it once to take the server's name when none was given. It doesn't implement `serve()`, because a dropped link must not end the local chat.
- The connector refuses a server that only speaks the handshake era. Each request is independent; a failed call answers `error` ("could not reach …"), and the client is reopened lazily on the next question.
- **Transport:** Streamable HTTP only, `url=…, token=…` with a `Bearer` header, or `server=…` for an in-process server in tests and embedding. There is no stdio transport on either side.
- `McpFrontend(name="master", *, token, host, port, credentials)`; the token is required, and the name is the frontend's peer name and the server's name. Its `serve()` awaits FastMCP's own `run_async(transport="http")`, with a `TokenVerifier` that compares the bearer token in constant time, and `shutdown()` cancels it.
- *Alternative: stdio as well.* Dropped: a session served over MCP is reached from another machine, and one transport, always behind a token, keeps both ends simpler.

### 9. Packaging
- `McpConnector` lives in `chatinho/connectors/mcp.py` and `McpFrontend` in a new `chatinho/frontends/mcp.py`, next to the other batteries of their kind. Each end keeps its own half of the wire format — the frontend writes the result, the connector reads it — and a test checks they agree. They import `mcp` and are exposed through the lazy `__getattr__`, with the `mcp` extra in the missing-extra message.
- `connectors/__init__.py` and `frontends/__init__.py` resolve their names on first use (PEP 562). Before this, importing any connector imported all of them, so `McpConnector` would have needed `requests` and `openai` too.
- `pyproject.toml` gains `mcp = ["fastmcp>=4.0"]`, and `all` and `dev` include it.
- `docs/SPEC.md` documents `msg.credentials` under `HookSay`, and the architecture tests' extras check covers `mcp`.

## Risks / Trade-offs

- **A say in a room with one peer that answers is now asked of it**, in every chatinho session. In a local chat with one agent, everything the user says goes to it, with or without `@name`. → That is the intent; with two agents nothing changes, and replies and commands' output stay broadcasts.
- **Remote peers cannot tell clients apart.** Every remote question comes from the frontend (`master`). → The routing back is exact, since it is by message id. A peer that must know who asked is a case for a later field on the message.
- **Attachment bytes through `locate`** depend on a linking backend. → The server documents it and the result says when attachments couldn't be returned. A byte-level grant is a follow-up.
- **The `mcp` extra pulls in pydantic and other compiled packages**, so it's heavy on Termux. → It's optional, and the core stays dependency-free.
- **A message's credentials are visible to every peer that hears it**, not only the one that answers: listeners get the same message. → They are cleared once the message is answered; a session that lends keys should trust its own peers.
- **A delegated credential is readable by the remote session's code while it answers.** Delegation reduces exposure (one question, memory only) but cannot prevent a dishonest or buggy remote from copying it. → It's opt-in, the system should be served over HTTPS, and the docs recommend a sub-key with a spending limit or a short-lived token.
- **HTTP exposes every peer.** → The bearer token is mandatory on HTTP. The token and URL are the connector's configuration and are never sent to the server's peers.
- **The client must know the remote peer's name.** → `peers` lists them, and `McpConnector` picks the only answering one by itself.
- **A peer that never answers** keeps the call waiting, since there is no deadline. → The client's own call timeout bounds it, and ending the call lets go of the question and its credentials.
- **Names are not unique across machines.** → They're used only for display.

## Migration Plan

This is additive except for one rule: in a room where exactly one peer answers, a say that is not a reply is now asked of that peer. Chats with several peers that answer, `ask`, and `Reply` without a status keep their behavior. To roll back, remove the extra and revert the change.

## Open Questions

- **Peer router:** how a remote session should pick the answering peer when it has several; this change only leaves room for it.
