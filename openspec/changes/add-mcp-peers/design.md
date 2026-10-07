# Design

## Context

See proposal.md for why. What the code has today, and what shapes the approach:

- A frontend is a peer at `LOCAL` declared with `@frontend`; `ChatApp` gets every capability through grants (`say`, `ask`, `context`, `peers`, `commands`, `invoke`, `locate`). `session.run()` runs every peer's `serve()` and closes when the first one returns, calling `shutdown()` on each peer.
- `add_connector` works on a running session: calling `start()` again starts the new peer's queue task. There is no way to remove a peer.
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
- Every piece is testable offline, over in-memory MCP streams.

**Non-Goals:**
- Routes through several sessions (multi-hop) and choosing a remote peer from the client.
- A peer router. Until there is one, the remote session sends a question to its only peer, or says it to the room.
- Broadcasts from the client, notifications, and resource subscriptions.
- Remote peers mirrored one-to-one in the local roster.
- Remote peers asking the remote asker a question (MCP elicitation); the frontend answers such questions with `error`. A remote peer that needs more information answers with status `asked` instead, and the asker's next question continues the conversation.

## Decisions

### 1. Core additions stay small and generic
- **`Reply.status`** (`answered` | `asked` | `error`, default `answered`; "I don't know" is an `answered` text) and **`ask(..., detail=True) -> Answer(text, status, msg_id)`.** The session already resolves the pending future from the answer message; with `detail` it resolves it with the `Answer` instead of the text. The default path is untouched.
- **`HookCredential` and `HookServeCredential`** (decision 5).
- *Alternative: MCP sampling, relaying each completion back to the asker.* It was in an earlier draft. It is dropped: it is deprecated in the modern protocol, it costs a round trip per completion, and credential delegation covers the same need.
- **A failing `answer` fails the `ask`.** Today a peer that raises in `answer` leaves its asker waiting forever. The session now sets the exception on the waiting ask, so a direct question to a failing peer ends in `error` at once, as the one-result guarantee needs.
- **No core change for clients.** The frontend listens and resolves its own waits (decisions 3 and 4), and adds or removes no peer, so the rule that a `say` is owed to nobody stays true in the core.

### 2. Wire format: one tool per verb, structured results
`McpFrontend` uses the SDK's low-level `Server` (`on_list_tools`, `on_call_tool`), for full control over tool schemas and the request context.
- **Tools:** `ask`, `list_peers`, `list_commands`, `invoke`, `read_attachment`.
- **`ask` arguments:** `text`, `asker?`, `deadline_ms?`. There is no peer name: the session decides who answers.
- **Result:** structured content `{status, text, attachments: [{name, media_type, data_b64}]}`, also rendered as text for clients that only read text. `error` and `timeout` set `isError`.
- *Alternative: FastMCP decorators.* They're quicker to write but hide the request context needed for client names and lent credentials.

### 3. The frontend speaks for every client
The frontend is the session's peer zero, as a terminal is, and it handles every client itself.
- **Receive:** an `ask` tool call arrives, carrying its client's name in `_meta` `clientInfo.name`, made safe (no `/`, non-empty, `client` when missing).
- **Forward:** the frontend puts the text into the session as its own message, with `ask` or `say` (decision 4).
- **Route back:** it maps that message's id to the open question, which belongs to that client's call. The reply to that message resolves that question alone, and the result goes back on that client's call.
- **Several clients:** their questions are open at once, each under its own message id. Opening a question holds a lock for one step, so each finds its own message.
- **Follow-ups:** the frontend keeps the last answer per `(client, asker)`, using the `asker` name the connector sends.
- **Asking the frontend:** a peer that asks it gets `Reply("Nobody is at this session's terminal…", status="error")`. An answer that arrives after its question ended is only heard.
- *Alternative, the earlier draft: one proxy peer per asker, named `<client>/<asker>`.* It let remote peers tell askers apart, but it needed peers added and removed at run time (`remove_connector`, idle expiry). It is dropped: the frontend manages the connections, and the core stays as it is.

### 4. Who answers, deadlines and the one-result guarantee
The answering peers are those in `peers()` that declare `HookAnswer`, excluding the frontend.
- **One peer:** the frontend's own `ask(id, text, detail=True)`, awaited against the deadline.
- **Several peers:** the frontend `say`s the question and registers a future under the said message id. Its `listen` resolves that future with the first message whose `reply_to` is that id; later replies only stay in the conversation. The wait is `asyncio.wait_for(future, deadline)`.
- **Follow-ups:** with one peer, the next question is a new `ask` to that peer, so the peer has the history. With several, the frontend remembers each asker's last answer in the room and says the next question with `reply_to` set to it, so the peer that answered sees it is for it. A reply in the room is always `answered` (a `say` carries no status), so a question back cannot be told apart there; replying to the last answer covers it.
- **Several peers, none listening:** a `say` reaches only peers that declare `HookListen`, so if none of the answering peers listens, nobody could ever reply. The result is `error` at once ("several peers and none listens; a peer router is needed") rather than a `timeout` after the whole deadline.
- **No peer:** `error` at once.
- *Alternative: let the client name the peer.* That's what a route did; it is dropped to keep one hop and let the remote side own routing, which a peer router will take over.

Every outcome maps to one result:

| Outcome | Status |
|---|---|
| The only peer answered | the `Answer`'s status |
| A peer replied to the broadcast | `answered` |
| `asyncio.TimeoutError` | `timeout` |
| No answering peer | `error` |
| Several answering peers, none listening | `error` |
| The peer raised | `error` |

The default deadline is configurable (`McpFrontend(deadline=…)`, 120 s when not set); `McpConnector(deadline=…)` sends one with every question.

### 5. Credential delegation (opt-in)
This follows A2A's principle: credentials travel out of band, the server declares what it needs, and a short-lived, scoped credential is preferred to a master key.
- **Core:** `HookCredential` (grant `credential(msg_id, name)`) and `HookServeCredential` (demands `serve_credential`), keyed by the question being answered (the direct question or the broadcast one), served by the frontend, and otherwise raising `CredentialUnavailable`.
- **Declaration:** `McpFrontend(credentials={"llm": "OpenAI-compatible API key"})` announces the names in its `server/discover` result, as the capability extension `chatinho/credentials` (SEP-2133 `capabilities.extensions`). Undeclared names are dropped on arrival.
- **Delivery:** `McpConnector(delegate={"llm": value | callable})` discovers the server first, then puts the declared credentials in the `ask` request's `_meta["chatinho/credentials"]`. A callable is called per question, so it can mint short-lived tokens. Over HTTP the connector delegates only to `https` URLs or loopback hosts.
- **Lifetime:** the server keeps a dict from question message id to credentials, holding values in a `Secret` wrapper whose `repr` is redacted. The entry is popped in the `finally` of `ask`, so it is gone on every outcome, including `timeout`. Nothing goes to the message, the store or logs.
- **Not passed on:** the credential reaches only the session the connector connects to. A peer that obtained it through `credential` must not delegate it further; a connector only delegates its own `delegate` configuration.
- **Using it:** a peer (for example orbe's agent) reads `credential(msg.id, "llm")` and builds its model with that key for this answer only; without one, it answers without a model or with its own.
- *Alternative: put the key in the question text or a session-wide setting.* That leaks into history and outlives the question.

### 6. Attachments
- With the answer's message id (from `Answer.msg_id`, or the id of the reply to a broadcast), the frontend reads each attachment through `locate` (the backend's `file://` link) and returns its bytes base64-encoded.
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
- **Transports:** `command=[…]` for stdio, or `url=…, token=…` for HTTP with a `Bearer` header; `deadline` is optional.
- `McpFrontend(name="master", transport="stdio" | "http", host, port, token, deadline, credentials)`; the name is the frontend's peer name and the server's name. Its `serve()` runs the server over `stdio_server`, or a Uvicorn app with the SDK's Streamable HTTP app and a bearer-token check.

### 9. Packaging
- `chatinho.mcp` imports `mcp` and is exposed through the lazy `__getattr__` as `McpFrontend` and `McpConnector`, with the `mcp` extra in the missing-extra message.
- `pyproject.toml` gains `mcp = ["mcp>=2.3"]`, and `all` and `dev` include it.
- `docs/SPEC.md` documents `HookCredential` and `HookServeCredential`, and the architecture tests' extras check covers `mcp`.

## Risks / Trade-offs

- **Remote peers cannot tell clients apart.** Every remote question comes from the frontend (`master`). → The routing back is exact, since it is by message id. A peer that must know who asked is a case for the peer router, or for a later field on the message.
- **Attachment bytes through `locate`** depend on a linking backend. → The server documents it and the result says when attachments couldn't be returned. A byte-level grant is a follow-up.
- **Client names are self-declared.** Any client can claim to be `lab`, and on a stateless protocol nothing ties a request to an earlier one. → On HTTP every client already holds the same bearer token, so names only group follow-ups; they are not trusted.
- **The `mcp` extra pulls in pydantic and other compiled packages**, so it's heavy on Termux. → It's optional, and the core stays dependency-free.
- **A delegated credential is readable by the remote session's code while it answers.** Delegation reduces exposure (one question, memory only) but cannot prevent a dishonest or buggy remote from copying it. → It's opt-in, HTTPS-only, and the docs recommend a sub-key with a spending limit or a short-lived token.
- **HTTP exposes every peer.** → The bearer token is mandatory on HTTP. The token and URL are the connector's configuration and are never sent to the server's peers.
- **With several peers, the first reply wins, whoever it is.** A chatty peer can answer before the right one. → The others still reply into the conversation, and a peer router is the planned fix.
- **A broadcast nobody replies to** waits for the whole deadline. → It ends in `timeout`, which is still one result; peers that cannot help should stay quiet rather than reply.
- **Names are not unique across machines.** → They're used only for display.

## Migration Plan

This is additive: existing sessions, frontends and peers are unchanged. `ask` without `detail`, and `Reply` without a status, keep their behavior. To roll back, remove the extra and revert the change.

## Open Questions

- **Peer router:** how a remote session should pick the answering peer when it has several; this change only leaves room for it.
- **Should `list_peers` also describe each peer**, with a description declared on the class? It's useful for clients, but can be added later without changing the tools.
