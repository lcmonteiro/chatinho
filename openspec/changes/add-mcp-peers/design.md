# Design

## Context

See proposal.md for why. What the code has today, and what shapes the approach:

- A frontend is a peer at `LOCAL` declared with `@frontend`; `ChatApp` gets every capability through grants (`say`, `ask`, `context`, `peers`, `commands`, `invoke`, `locate`). `session.run()` runs every peer's `serve()` and closes when the first one returns, calling `shutdown()` on each peer.
- `add_connector` works on a running session: calling `start()` again starts the new peer's queue task. There is no way to remove a peer.
- `ask` returns the answer's text only. `@require(HookAsk, timeout=…)` is documented but not enforced anywhere.
- Attachments go to the backend that declares `HookKeep`, under the message id; anyone with `locate` can get a link to them. With no keeping backend they are dropped.
- The core is standard library only; batteries are lazy names behind extras, and `tests/test_architecture.py` checks that (and that `docs/SPEC.md` documents every hook).
- The official `mcp` SDK (2.3) provides what is needed: a low-level `Server`, `ServerSession.create_message` (sampling) and `client_params` (the client's name), a `ClientSession` with `sampling_callback` and `client_info`, stdio and Streamable HTTP transports, and in-memory streams for tests.

## Goals / Non-Goals

**Goals:**
- One peer in the local chat reaches any peer of any session along a route, and always gets one answer back.
- A remote peer's LLM calls are paid by the session that asked. By default no key crosses the link; delegating one is opt-in and bounded to one question and one hop.
- Every piece is testable offline, over in-memory MCP streams.

**Non-Goals:**
- Broadcasts across the link, notifications, and resource subscriptions.
- Remote peers mirrored one-to-one in the local roster.
- Remote peers asking the remote asker a question (MCP elicitation); a proxy answers such questions with `error`. A remote peer that needs more information answers with status `asked` instead, and the asker's next question continues the conversation.

## Decisions

### 1. Core additions stay small and generic
- **`ChatSession.remove_connector(peer_id)`:** cancel the peer's drain task, drop its queue and connector entry, and fail its pending `ask` futures with `PeerRemoved`. Its messages stay in the store. `LOCAL` cannot be removed.
- **`Reply.status`** (`answered` | `asked` | `error`, default `answered`; "I don't know" is an `answered` text) and **`ask(..., detail=True) -> Answer(text, status, msg_id)`.** The session already resolves the pending future from the answer message; with `detail` it resolves it with the `Answer` instead of the text. The default path is untouched.
- **`HookSample` (grant `sample`) and `HookServeSample` (demands `serve_sample`).** `sample(msg_id, messages, *, max_tokens=None, system=None)` is bound to nothing but the session: the session calls the frontend's `serve_sample` if it declares the hook, else raises `SamplingUnavailable`. Sampling is keyed by the message being answered because that is the only thing every peer already has, and it is what identifies whose question it is.
- *Alternative: pass a model object to each peer.* That would tie the core to an LLM API and could not follow the asker across hops.

### 2. Wire format: one tool per verb, structured results
`McpServerFrontend` uses the SDK's low-level `Server`, for full control over tool schemas and per-connection state.
- **Tools:** `ask`, `list_peers`, `list_commands`, `invoke`, `read_attachment`.
- **`ask` arguments:** `route: [str]`, `text`, `deadline_ms?`, `asker: [str]`, `visited: [str]`.
- **Result:** structured content `{status, text, hop, attachments: [{name, media_type, data_b64}]}`, also rendered as text for clients that only read text. `error` and `timeout` set `isError`.
- *Alternative: FastMCP decorators.* They're quicker to write but hide the per-session hooks needed for proxies and sampling.

### 3. One proxy peer per asker
- For each `(client connection, asker path)`, the frontend adds an `_AskerProxy` peer, named `"/".join([client_name, *asker])` (for example `lab/me`).
  - The proxy declares `HookAsk` to ask, and `HookAnswer`, answering any question put to it with `Reply("…cannot be asked…", status="error")`.
  - It's added with `add_connector` + `start()`.
- **Bookkeeping:** the frontend maps proxy id → client connection, and connection → proxy ids.
  - **stdio:** a single connection, which ends with `serve()`.
  - **HTTP:** connections are tracked through the session manager's lifecycle. When a connection ends, its proxies are removed with `remove_connector`.
- The client name comes from `ServerSession.client_params.clientInfo.name`, made safe (no `/`, non-empty).

### 4. Asking, deadlines and the one-result guarantee
`ask` resolves `route[0]` by name among `peers()`, excluding the frontend and proxies. Then, from the asker's proxy:
- **Last hop (`len(route) == 1`):** `asyncio.wait_for(proxy.ask(id, text, detail=True), remaining)`.
- **More hops:** the target must be an `McpConnector`. It's asked with `route[1:]`, the remaining deadline and `visited + [self.session_id]`. They're passed as arguments of a dedicated method, `forward(...)`, rather than parsed from text, so a route can never be spoofed by message content.

Every outcome maps to one result:

| Outcome | Status |
|---|---|
| The peer answered | the `Answer`'s status |
| `asyncio.TimeoutError` | `timeout` |
| No such peer | `error` |
| The peer raised | `error` |
| Not a forwarder | `error` |
| `PeerRemoved` | `error` |
| Loop, or hop limit reached | `error` |

`hop` is this session's route prefix, joined with whatever the next hop returned. The default deadline is configurable (`McpServerFrontend(deadline=…)`, 120 s when not set); `McpConnector(deadline=…)` sends one with every question it starts. Each hop subtracts a 250 ms margin, so inner hops finish first.

### 5. Attachments
- With an `Answer.msg_id`, the frontend reads each attachment through `locate` (the backend's `file://` link) and returns its bytes base64-encoded.
- The names are the relative link targets in the answer's text. In chatinho a message links its attachments by name, and backends have no way to list a message's attachments. Each name is `locate`d, and names that resolve to nothing are skipped. A session without a linking backend returns no attachments, and the text says so.
- On the asking side, `McpConnector` turns them back into `Attachment`s on its reply, so the local backend keeps them.
- *Alternative: a new grant to fetch attachment bytes.* That's cleaner, but it widens the core more than this change needs. It's noted as follow-up.

### 6. Sampling across hops
- **In B, `serve_sample(msg_id, …)`:** look up `msg_id`. If the question came from a proxy, send `create_message` on that proxy's client connection and return the text. Otherwise raise `SamplingUnavailable`.
- **In A, `McpConnector`'s `sampling_callback` for a question it is forwarding:** the request is relayed upward with `self.sample(question_msg_id, …)`, which goes to A's own frontend. The connector keeps a map from its in-flight forward to the local question message.
- **For a question that started locally:** the connector calls the `sample_with` function it was given, for example orbe's `openai_model()`. With neither available, it declines.
- Sampling sends no key, and keys never appear in any message.

### 7. Credential delegation (opt-in)
This follows A2A's principle: credentials travel out of band, the server declares what it needs, and a short-lived, scoped credential is preferred to a master key.
- **Core:** `HookCredential` (grant `credential(msg_id, name)`) and `HookServeCredential` (demands `serve_credential`), mirroring sampling: keyed by the message being answered, served by the frontend, and otherwise raising `CredentialUnavailable`.
- **Declaration:** `McpServerFrontend(credentials={"llm": "OpenAI-compatible API key"})` announces the names in the initialize result's `capabilities.experimental["chatinho/credentials"]`. Undeclared names are dropped on arrival.
- **Delivery:** `McpConnector(delegate={"llm": value | callable})` puts the declared ones in the `ask` request's `_meta["chatinho/credentials"]`. A callable is called per question, so it can mint short-lived tokens. Over HTTP the connector delegates only to `https` URLs or loopback hosts.
- **Lifetime:** the server keeps a dict from question message id to credentials, holding values in a `Secret` wrapper whose `repr` is redacted. The entry is popped in the `finally` of `ask`, so it is gone on every outcome, including `timeout`, and with the proxy on disconnect. Nothing goes to the message, the store or logs.
- **No forwarding:** `forward(...)` takes no credentials argument, so a forwarding connector cannot pass on what it received; it only adds its own `delegate` configuration.
- **Priority for peers:** a peer (for example orbe's agent) may try `credential` first and fall back to `sample`.
- *Alternative: put the key in the question text or a session-wide setting.* That leaks into history and outlives the question.
- *Alternative: forward credentials along the route.* That multiplies who holds the key, which A2A also avoids.

### 8. Addressing in the local chat
- **Parsing:** `McpConnector` listens to local broadcasts and parses a leading `@<name>(/seg)*` followed by whitespace. A message without its name is ignored.
- **Direct asks:** for a direct ask to the connector, the same prefix is optional, and the default peer is used without one.
- **Asker path:** the connector sends the asking peer's name, split on `/`. For the local user that's the frontend's name (for example `me`). For a proxy it's `lab/me`, which the next server prefixes with its client name. This gives the reverse route at every hop with one rule.

### 9. Connection lifecycle
- `McpConnector` opens its `ClientSession` in `initialize()` and closes it in `shutdown()`. It doesn't implement `serve()`, because a dropped link must not end the local chat.
- On a lost connection it reconnects lazily on the next question, and answers `error` ("could not reach …") if that fails.
- **Transports:** `command=[…]` for stdio, or `url=…, token=…` for HTTP with a `Bearer` header; `deadline` is optional.
- `McpServerFrontend(transport="stdio" | "http", host, port, token, deadline)`. Its `serve()` runs `stdio_server` or a Uvicorn app with the Streamable HTTP session manager and a bearer-token check.

### 10. Packaging
- `chatinho.mcp` imports `mcp` and is exposed through the lazy `__getattr__` as `McpServerFrontend` and `McpConnector`, with the `mcp` extra in the missing-extra message.
- `pyproject.toml` gains `mcp = ["mcp>=2.3"]`, and `all` and `dev` include it.
- `docs/SPEC.md` documents `HookSample`, `HookServeSample`, `HookCredential` and `HookServeCredential`, and the architecture tests' extras check covers `mcp`.

## Risks / Trade-offs

- **Pending futures on removal:** removing a proxy while a peer is answering its question. → The future fails with `PeerRemoved`, so nothing hangs; the answer message, if it comes, is still posted.
- **Attachment bytes through `locate`** depend on a linking backend. → The server documents it and the result says when attachments couldn't be returned. A byte-level grant is a follow-up.
- **Sampling support varies by client.** → Peers get `SamplingUnavailable` and answer with an error, which is still one result; orbe can fall back to a local model.
- **The `mcp` extra pulls in pydantic and other compiled packages**, so it's heavy on Termux. → It's optional, and the core stays dependency-free.
- **A delegated credential is readable by the first hop's code while it answers.** Delegation reduces exposure (one question, one hop, memory only) but cannot prevent a dishonest or buggy remote from copying it. → It's opt-in, HTTPS-only, and the docs recommend a sub-key with a spending limit or a short-lived token. Sampling stays the default.
- **HTTP exposes every peer.** → The bearer token is mandatory on HTTP. The token and URL are the connector's configuration and are never sent to other hops.
- **Names are not unique across machines.** → They're used only for display and routing, while loops are detected by random session ids.

## Migration Plan

This is additive: existing sessions, frontends and peers are unchanged. `ask` without `detail`, and `Reply` without a status, keep their behavior. To roll back, remove the extra and revert the change.

## Open Questions

- **Should `list_peers` also describe each peer**, with a description declared on the class? It's useful for clients, but can be added later without changing the tools.
