# Proposal

## Why

A chatinho session today lives on one machine: its peers can only be reached from its own terminal, and the only remote link is `A2AConnector`, which posts one question to a fixed HTTP endpoint and sends its API key along. We want a chat on one machine to ask a session on another — the peers of a lab server from a laptop's chat — and we want a remote peer that needs an LLM to use the intelligence of whoever asked, without that person's API key ever leaving their machine by default. MCP gives both: a standard transport for tools, and *sampling*, which lets a server ask its client to run a completion.

## What Changes

- Add `McpFrontend`, a `@frontend`, named `master` by default, that turns a headless session into an MCP server. It takes the place of the terminal: MCP clients ask the session questions and run its commands through it. Several clients may be connected at once.
- Add `McpConnector`, an ordinary `@connector` that connects to such a server. It appears in the local chat under a name it chooses (for example `@lab`) and sends the questions addressed to it to the remote session.
- One hop only: the client sends the question to the remote session, not to a named remote peer, and the remote session decides who answers. With exactly one peer able to answer, the question is asked to it directly. With several, the question is said to the room (a `say` from the asker) and the first reply to it is the answer; a peer router can replace this later.
- Messages across the link are always questions: a client cannot broadcast to the remote room on its own.
- Every question gets exactly one result — `answered`, `asked` (answered with a question back), `error` or `timeout` — within a deadline, configurable and 120 s by default. Attachments travel back with the answer.
- The frontend handles every client itself. It receives a question, forwards it into the session as its own `ask` or `say` (depending on how many peers can answer), and sends the reply to that message back to the client that asked. No peer is added or removed per client; inside the remote session, every remote question comes from the frontend (`master`).
- Add `HookSample`: a peer that needs an LLM asks for a completion on behalf of the message it is answering. Across the link the request is relayed as MCP sampling to the asking session, so that session's model and key do the work; sampling sends no key.
- Add opt-in credential delegation, following A2A's principle: the server declares the credentials its peers may use, a connector configured to delegate sends them out of band (MCP request metadata, HTTPS only), and the remote session keeps each one in memory only while that question is answered. A credential never enters message content or history. Peers get it through `HookCredential`.
- Let answers carry a status (`Reply(..., status="asked" | "error")`) and let askers get it with the answer's message id (`ask(..., detail=True)`), so answers are relayed faithfully, attachments included.
- Speak the modern MCP protocol (2026-07-28) only: no initialize handshake, the client's name and capabilities arrive with every request, and a server that needs something from the client mid-call (a sample) returns an `InputRequiredResult` that the client fulfils and retries. MCP sampling is deprecated in this protocol revision (SEP-2577) but still part of it; credential delegation is the way forward if it goes away.
- Package the MCP pieces behind a new `chatinho[mcp]` extra; the core stays standard library only.
- Out of scope: routes through several sessions (multi-hop), choosing a remote peer from the client, a peer router, broadcasts from the client, sending API keys implicitly or in message content, and mirroring each remote peer as its own peer in the local roster.

## Capabilities

### New Capabilities
- `answer-details`: answer statuses on `Reply`, and `ask(..., detail=True)` returning the text, status and answer message id.
- `sampling`: `HookSample` — a peer asking for a completion on behalf of a message, and who serves it.
- `credential-delegation`: `HookCredential`, credentials declared by the server, delegated out of band by the connector, and alive only while their question is answered.
- `mcp-server`: `McpFrontend` — the MCP interface of a session, forwarding each client's question and routing the reply back, who answers a question (the only peer, or the first reply in the room), the one-result guarantee, deadlines and relaying sampling to the client.
- `mcp-connector`: `McpConnector` — naming, addressing from the local chat, sending questions, bringing back answers and attachments, and serving sampling with the local model.

### Modified Capabilities
<!-- None: attachments and message ids keep their contracts; answers that cross the link use them unchanged. -->

## Impact

- `src/chatinho/chat_session.py`: serving the new `sample` and `credential` grants; a peer whose `answer` raises fails the waiting `ask`.
- `src/chatinho/chat_message.py`: `Reply.status` and the `Answer` type.
- `src/chatinho/chat_hooks.py`: `HookSample`, `HookServeSample`, `HookCredential`, `HookServeCredential` and their protocols; `ask(..., detail=True)`; `docs/SPEC.md` gains their sections (the architecture test requires one per hook).
- New `src/chatinho/mcp/` package (`frontend.py`, `connector.py`, wire helpers), exported lazily as `McpFrontend` and `McpConnector`.
- `pyproject.toml`: an `mcp` extra (the official `mcp` SDK), also added to `all` and `dev`; `uv.lock` updated.
- `README.md`, `CLAUDE.md`, an example under `examples/` for a headless MCP session.
- Security: an HTTP server lets clients put questions to every peer of the session and spend their own model through it; the HTTP transport requires a bearer token. A client only ever spends its own key. With sampling, the remote session never holds one; with delegation, which is opt-in, the remote session holds a credential in memory for one question — so the docs recommend a sub-key with a spending limit or a short-lived token, never the main key.
