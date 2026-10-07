# Design

## Context

See proposal.md for why. What the code has today, and what shapes the approach:

- A frontend is a peer at `LOCAL` declared with `@frontend`; `ChatApp` gets every capability through grants (`say`, `ask`, `context`, `peers`, `commands`, `invoke`, `locate`). `session.run()` runs every peer's `serve()` and closes when the first one returns, calling `shutdown()` on each peer.
- `ask` returns the answer's text only. `@require(HookAsk, timeout=…)` is documented but not enforced anywhere.
- Attachments go to the backend that declares `HookKeep`, under the message id; anyone with `locate` can get a link to them. With no keeping backend they are dropped.
- A `say` is a broadcast, and a reply to it is another `say` with `reply_to`. Nothing is owed back, so nothing resolves for the sayer; a peer that declares `HookListen` hears every message, including those replies.
- The core is standard library only; batteries are lazy names behind extras, and `tests/test_architecture.py` checks that (and that `docs/SPEC.md` documents every hook).
- The official `mcp` SDK (2.3) speaks two protocol eras. The handshake era (2025-11-25) has `initialize`, a session per connection and server-to-client requests. The modern era (2026-07-28), which this change targets, is stateless:
  - `server/discover` replaces the handshake.
  - Every request carries the client's info and capabilities in `_meta` (`io.modelcontextprotocol/clientInfo`, `…/clientCapabilities`).
  - The SDK's high-level `Client` can also connect to a `Server` in-process, which the tests use.
- Sampling (a server asking its client for a completion) is deprecated in 2026-07-28 (SEP-2577). This change does not use it.

## Goals / Non-Goals

**Goals:**
- One peer in the local chat puts a question to a remote session, and always gets one answer back.
- A remote peer's LLM calls are paid by the session that asked. Paying for them is done by delegating a credential, opt-in and bounded to one question.
- Every piece is testable offline, with the SDK's in-process MCP client.

**Non-Goals:**
- Routes through several sessions (multi-hop) and choosing a remote peer from the client.
- A peer router. Until there is one, the remote session sends a question to its only peer, or says it to the room.
- Notifications and resource subscriptions.
- Remote peers mirrored one-to-one in the local roster.
- Remote peers asking the remote asker a question (MCP elicitation); the frontend answers such questions with `error`. A remote peer that needs more information answers with status `asked` instead, and the asker's next question continues the conversation.

## Decisions

### 1. Core additions stay small and generic
- **`Reply.status`**, a `ReplyStatus` `str` enum (`ANSWERED` | `ASKED` | `ERROR`, default `ANSWERED`; "I don't know" is an `answered` text), carried on the answer's **`ChatMessage.status`**. Whoever hears or reads the reply sees what it said about itself; `ask` still returns the text. The archive does not keep the status.
- **A say in a room with one peer that answers is asked of it.** `say` addresses the message to that peer when it is not a reply, is not from a command, and exactly one peer other than the speaker and the frontend declares `HookAnswer`. Its `answer` is called, and the reply comes back with `reply_to` set to the say. Listeners still hear both. This makes a room with one agent a conversation with it, and it is what lets the MCP bridge use one verb.
- *Alternative, the earlier draft: `ask(..., detail=True) -> Answer(text, status, msg_id)`.* It gave the frontend the status and the answer's id, but only for its own asks. With the status on the message and a say that asks the lone peer, the frontend just says and listens, and `detail` goes.
- **Credentials on the message:** `ChatMessage.credentials`, set through `say(..., credentials=…)` (decision 5).
- *Alternative: MCP sampling, relaying each completion back to the asker.* It was in an earlier draft. It is dropped: it is deprecated in the modern protocol, it costs a round trip per completion, and credential delegation covers the same need.
- **A failing `answer` is a reply.** Today a peer that raises in `answer` leaves its asker waiting forever. The session now sets the exception on a waiting ask, and when nobody awaits the message (a say asked of the lone peer) it posts an `error` reply to it, so the bridge ends in `error` at once.
- **No peer per client.** The frontend listens and resolves its own waits (decisions 3 and 4), and adds or removes no peer.

### 2. Wire format: one tool, a bridge
`McpFrontend` uses the SDK's low-level `Server` (`on_list_tools`, `on_call_tool`), for full control over the tool schema and the request context.
- **Tool:** `say` only. The server is a bridge: it publishes what a client says in the session and returns the first reply. There is no tool to list peers or commands, run commands, or read attachments later; attachments come back with the reply.
- **`say` arguments:** `text`, `asker?`, `deadline_ms?`. There is no peer name: the session decides who replies.
- **Result:** structured content `{status, text, attachments: [{name, media_type, data_b64}], msg_id}`, where `msg_id` is the reply's message id in the remote session (absent when no reply arrived),, also rendered as text for clients that only read text. `error` and `timeout` set `isError`.
- **Read back:** `McpConnector` turns the result straight into its local `Reply`: `answered` keeps the text and attachments, `asked` becomes `ReplyStatus.ASKED`, and `error` and `timeout` become `ReplyStatus.ERROR` with the status named in the text.
- *Alternative: FastMCP decorators.* They're quicker to write but hide the request context needed for client names and lent credentials.

### 3. The frontend speaks for every client
The frontend is the session's peer zero, as a terminal is, and it handles every client itself.
- **Receive:** a `say` tool call arrives, carrying its client's name in `_meta` `clientInfo.name`, made safe (no `/`, non-empty, `client` when missing).
- **Forward:** the frontend says the text in the session as its own message (decision 4).
- **Route back:** it maps that message's id to the open question, which belongs to that client's call. The reply to that message resolves that question alone, and the result goes back on that client's call.
- **Several clients:** their messages wait at once, each under its own message id, which `say` returns straight away.
- **Follow-ups:** the frontend keeps the last answer per `(client, asker)`, using the `asker` name the connector sends.
- **Asking the frontend:** a peer that asks it gets `Reply("Nobody is at this session's terminal…", status="error")`. An answer that arrives after its question ended is only heard.
- *Alternative, the earlier draft: one proxy peer per asker, named `<client>/<asker>`.* It let remote peers tell askers apart, but it needed peers added and removed at run time (`remove_connector`, idle expiry). It is dropped: the frontend manages the connections, and the core stays as it is.

### 4. Who answers, deadlines and the one-result guarantee
The answering peers are those in `peers()` that declare `HookAnswer`, excluding the frontend.
- **Always a say:** the frontend `say`s the text and registers a future under the said message id. With one answering peer, the session asks it of that peer (decision 1); with several, it goes to the room. Its `listen` resolves the future with the first message whose `reply_to` is that id; later replies only stay in the conversation. The wait is bounded by the deadline.
- **Follow-ups:** with one peer, the next message is a new say, asked of that peer, so the peer has the history. With several, the frontend remembers each asker's last reply in the room and says the next message with `reply_to` set to it, so the peer that replied sees it is for it. With one peer the follow-up must not be a reply, or the session would not ask it.
- **Several peers, none listening:** a `say` reaches only peers that declare `HookListen`, so if none of the answering peers listens, nobody could ever reply. The result is `error` at once ("several peers and none listens; a peer router is needed") rather than a `timeout` after the whole deadline.
- **No peer:** `error` at once.
- *Alternative: let the client name the peer.* That's what a route did; it is dropped to keep one hop and let the remote side own routing, which a peer router will take over.

Every outcome maps to one result:

| Outcome | Status |
|---|---|
| The reply arrived | the reply message's `status` |
| `asyncio.TimeoutError` | `timeout` |
| No answering peer | `error` |
| Several answering peers, none listening | `error` |
| The lone peer raised | `error` (its error reply) |

The default deadline is configurable (`McpFrontend(deadline=…)`, 120 s when not set); `McpConnector(deadline=…)` sends one with every question.

### 5. Credential delegation (opt-in)
This follows A2A's principle: credentials travel out of band, the server declares what it needs, and a short-lived, scoped credential is preferred to a master key.
- **Core:** the credentials ride on the message as metadata, `ChatMessage.credentials` (keys by name, each a `Secret`), set by `say(..., credentials=…)`. The peer that answers a message reads them from that message, so the key it uses belongs to the message, and one peer can work with a different key for each message.
- *Alternative, the earlier draft: a `HookCredential` grant served by the frontend (`credential(msg_id, name)`).* It worked, but it was a second path to what the message itself can carry.
- **Declaration:** `McpFrontend(credentials={"llm": "OpenAI-compatible API key"})` announces the names in its `server/discover` result, as the capability extension `chatinho/credentials` (SEP-2133 `capabilities.extensions`). Undeclared names are dropped on arrival.
- **Delivery:** `McpConnector(delegate={"llm": value | callable})` discovers the server first, then puts the declared credentials in the `say` request's `_meta["chatinho/credentials"]`. A callable is called per question, so it can mint short-lived tokens. Over HTTP the connector delegates only to `https` URLs or loopback hosts.
- **Lifetime:** the frontend builds the mapping of `Secret`s from the request, says the message with it, and clears that same mapping in the `finally` of the `say` call, so it is gone on every outcome, including `timeout`. The text, the store and logs never hold it, and `ChatMessage`'s `repr` leaves it out.
- **Not passed on:** the credential reaches only the session the connector connects to. A peer that found it on a message must not delegate it further; a connector only delegates its own `delegate` configuration.
- **Using it:** a peer (for example orbe's agent) reads `msg.credentials.get("llm")` and builds its model with that key for this message only; without one, it answers without a model or with its own.
- *Alternative: put the key in the question text or a session-wide setting.* That leaks into history and outlives the question.

### 6. Attachments
- With the reply's message id, the frontend reads each attachment through `locate` (the backend's `file://` link) and returns its bytes base64-encoded.
- The names are the relative link targets in the answer's text. In chatinho a message links its attachments by name, and backends have no way to list a message's attachments. Each name is `locate`d, and names that resolve to nothing are skipped. A session without a linking backend returns no attachments, and the text says so.
- On the asking side, `McpConnector` turns them back into `Attachment`s on its reply, so the local backend keeps them.
- *Alternative: a new grant to fetch attachment bytes.* That's cleaner, but it widens the core more than this change needs. It's noted as follow-up.

### 7. Addressing in the local chat
- **Parsing:** `McpConnector` listens to local broadcasts and takes those that start with `@<name>` followed by whitespace. A message without its name is ignored.
- **Direct asks:** for a direct ask to the connector, the prefix is optional.
- **Asker:** the connector sends the asking peer's name; the frontend uses it only to keep that asker's follow-ups together.

### 8. Connection lifecycle
- `McpConnector` opens an SDK `Client` in modern mode (`mode="auto"`, which probes `server/discover`) in `initialize()`, and closes it in `shutdown()`. It doesn't implement `serve()`, because a dropped link must not end the local chat.
- The connector refuses a server that only speaks the handshake era. Each request is independent; a failed call answers `error` ("could not reach …"), and the client is reopened lazily on the next question.
- **Transport:** Streamable HTTP only, `url=…, token=…` with a `Bearer` header, or `server=…` for an in-process server in tests and embedding; `deadline` is optional. There is no stdio transport on either side.
- `McpFrontend(name="master", *, token, host, port, deadline, credentials)`; the token is required, and the name is the frontend's peer name and the server's name. Its `serve()` runs a Uvicorn app with the SDK's Streamable HTTP app behind a bearer-token check, and `shutdown()` stops it.
- *Alternative: stdio as well.* Dropped: a session served over MCP is reached from another machine, and one transport, always behind a token, keeps both ends simpler.

### 9. Packaging
- `McpConnector` lives in `chatinho/connectors/mcp.py` and `McpFrontend` in a new `chatinho/frontends/mcp.py`, next to the other batteries of their kind. Each end keeps its own half of the wire format — the frontend writes the result, the connector reads it — and a test checks they agree. They import `mcp` and are exposed through the lazy `__getattr__`, with the `mcp` extra in the missing-extra message.
- `connectors/__init__.py` and `frontends/__init__.py` resolve their names on first use (PEP 562). Before this, importing any connector imported all of them, so `McpConnector` would have needed `requests` and `openai` too.
- `pyproject.toml` gains `mcp = ["mcp>=2.3"]`, and `all` and `dev` include it.
- `docs/SPEC.md` documents `msg.credentials` under `HookSay`, and the architecture tests' extras check covers `mcp`.

## Risks / Trade-offs

- **A say in a room with one peer that answers is now asked of it**, in every chatinho session. In a local chat with one agent, everything the user says goes to it, with or without `@name`. → That is the intent; with two agents nothing changes, and replies and commands' output stay broadcasts.
- **Remote peers cannot tell clients apart.** Every remote question comes from the frontend (`master`). → The routing back is exact, since it is by message id. A peer that must know who asked is a case for the peer router, or for a later field on the message.
- **Attachment bytes through `locate`** depend on a linking backend. → The server documents it and the result says when attachments couldn't be returned. A byte-level grant is a follow-up.
- **Client names are self-declared.** Any client can claim to be `lab`, and on a stateless protocol nothing ties a request to an earlier one. → On HTTP every client already holds the same bearer token, so names only group follow-ups; they are not trusted.
- **The `mcp` extra pulls in pydantic and other compiled packages**, so it's heavy on Termux. → It's optional, and the core stays dependency-free.
- **A message's credentials are visible to every peer that hears it**, not only the one that answers: listeners get the same message. → They are cleared once the message is answered; a session that lends keys should trust its own peers.
- **A delegated credential is readable by the remote session's code while it answers.** Delegation reduces exposure (one question, memory only) but cannot prevent a dishonest or buggy remote from copying it. → It's opt-in, HTTPS-only, and the docs recommend a sub-key with a spending limit or a short-lived token.
- **HTTP exposes every peer.** → The bearer token is mandatory on HTTP. The token and URL are the connector's configuration and are never sent to the server's peers.
- **With several peers, the first reply wins, whoever it is.** A chatty peer can answer before the right one. → The others still reply into the conversation, and a peer router is the planned fix.
- **A broadcast nobody replies to** waits for the whole deadline. → It ends in `timeout`, which is still one result; peers that cannot help should stay quiet rather than reply.
- **Names are not unique across machines.** → They're used only for display.

## Migration Plan

This is additive except for one rule: in a room where exactly one peer answers, a say that is not a reply is now asked of that peer. Chats with several peers that answer, `ask`, and `Reply` without a status keep their behavior. To roll back, remove the extra and revert the change.

## Open Questions

- **Peer router:** how a remote session should pick the answering peer when it has several; this change only leaves room for it.
- **Listing peers or commands over MCP:** dropped to keep the bridge to one tool; it can come back as a second tool if clients need it.
