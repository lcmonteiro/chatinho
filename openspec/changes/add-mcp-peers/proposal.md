# Proposal

## Why

A chatinho session today lives on one machine: its peers can only be reached from its own terminal, and the only remote link is `A2AConnector`, which posts one question to a fixed HTTP endpoint and sends its API key along. We want sessions on different machines to reach each other's peers — ask `weather` on a lab server from a laptop's chat, through as many sessions as needed — and we want a remote peer that needs an LLM to use the intelligence of whoever asked, without that person's API key ever leaving their machine. MCP gives both: a standard transport for tools, and *sampling*, which lets a server ask its client to run a completion.

## What Changes

- Add `McpServerFrontend`, a `@frontend` that turns a headless session into an MCP server. It takes the place of the terminal: MCP clients ask the session's peers and run its commands through it. Several clients may be connected at once.
- Add `McpConnector`, an ordinary `@connector` that connects to such a server. It appears in the local chat under a name it chooses (for example `@lab`) and forwards questions to the remote session.
- Messages across the link are directed only: a client asks one named peer, never broadcasts. Addresses are routes, `@lab/office/weather`, consumed one hop at a time, so a question can travel through several sessions.
- Every question gets exactly one result — `answered`, `asked` (answered with a question back), `error` or `timeout` — within one end-to-end deadline, configurable and 120 s by default, with the failing hop named. Attachments travel back with the answer.
- Inside a remote session, each asker appears as its own peer, with its own id, named by the reverse route (`lab/me`, then `office/lab/me` one hop further); it is removed when its client disconnects.
- Add `HookSample`: a peer that needs an LLM asks for a completion on behalf of the message it is answering. Across MCP links the request is relayed as MCP sampling back to the session where the question started, so that session's model and key do the work; sampling sends no key.
- Add opt-in credential delegation, following A2A's principle: the server declares the credentials its peers may use, a connector configured to delegate sends them out of band (MCP request metadata, HTTPS only), and the remote session keeps each one in memory only while that question is answered. A credential never enters message content or history and is never forwarded past the first hop. Peers get it through `HookCredential`.
- Let answers carry a status (`Reply(..., status="asked" | "error")`) and let askers get it with the answer's message id (`ask(..., detail=True)`), so answers are relayed faithfully, attachments included.
- Add `ChatSession.remove_connector`, so peers can leave a running session. (Adding a peer to a running session already works: `start()` picks up peers attached since.)
- Loop protection: a hop limit and a list of opaque session ids visited.
- Package the MCP pieces behind a new `chatinho[mcp]` extra; the core stays standard library only.
- Out of scope: broadcast (`say`) across the link, sending API keys implicitly or in message content, and mirroring each remote peer as its own peer in the local roster.

## Capabilities

### New Capabilities
- `answer-details`: answer statuses on `Reply`, and `ask(..., detail=True)` returning the text, status and answer message id.
- `peer-lifecycle`: removing a peer from a running session, and what happens to its queue, pending questions and history.
- `sampling`: `HookSample` — a peer asking for a completion on behalf of a message, and who serves it.
- `credential-delegation`: `HookCredential`, credentials declared by the server, delegated out of band by the connector, alive only while their question is answered, and never forwarded.
- `mcp-server`: `McpServerFrontend` — the MCP interface of a session, per-asker proxy peers, the one-result guarantee, routes, deadlines, loop protection and relaying sampling to the client.
- `mcp-connector`: `McpConnector` — naming, addressing from the local chat, forwarding questions and attachments, and serving sampling with the local model.

### Modified Capabilities
<!-- None: attachments and message ids keep their contracts; answers that cross the link use them unchanged. -->

## Impact

- `src/chatinho/chat_session.py`: `remove_connector`; serving the new `sample` grant.
- `src/chatinho/chat_message.py`: `Reply.status` and the `Answer` type.
- `src/chatinho/chat_hooks.py`: `HookSample`, `HookServeSample`, `HookCredential`, `HookServeCredential` and their protocols; `ask(..., detail=True)`; `docs/SPEC.md` gains its section (the architecture test requires one per hook).
- New `src/chatinho/mcp/` package (`server.py`, `connector.py`, routing helpers), exported lazily as `McpServerFrontend` and `McpConnector`.
- `pyproject.toml`: an `mcp` extra (the official `mcp` SDK), also added to `all` and `dev`; `uv.lock` updated.
- `README.md`, `CLAUDE.md`, an example under `examples/` for a headless MCP session.
- Security: an HTTP server exposes every peer of the session and lets clients spend their own model through it; the HTTP transport requires a bearer token. A client only ever spends its own key. With sampling, a remote session never holds one; with delegation, which is opt-in, the first hop holds a credential in memory for one question — so the docs recommend a sub-key with a spending limit or a short-lived token, never the main key.
