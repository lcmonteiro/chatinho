# Proposal

## Why

A chatinho session today lives on one machine: its peers can only be reached from its own terminal, and the only remote link is `A2AConnector`, which posts one question to a fixed HTTP endpoint and sends its API key along. We want a chat on one machine to ask a session on another — the peers of a lab server from a laptop's chat — and we want a remote peer that needs an LLM to be able to use a credential the asker lends for that one question, the way A2A delegates credentials, rather than a key configured on the remote machine for everyone. MCP gives a standard transport for tools, and its request metadata carries the credential out of band.

## What Changes

- Add `McpFrontend`, a `@frontend`, named `master` by default, that turns a headless session into an MCP server. It takes the place of the terminal: MCP clients do what a person at the terminal can: `say` something and get the first reply, `ask` one peer by name, list the `peers`, list the session's `tools` (its slash commands) and `run` one. Several clients may be connected at once.
- Add `McpConnector`, an ordinary `@connector` that connects to such a server. It appears in the local chat under a name it chooses (for example `@lab`) and sends the questions addressed to it to the remote session.
- One hop only. With `say`, the client sends the message to the remote session, not to a named remote peer, and the remote session decides who answers. The frontend says the message in the remote session. With exactly one peer able to answer, the core rule asks that peer. With several, the message stays said to the room and the first reply to it is the answer; a peer router can replace this later. With `ask`, the client names the remote peer itself; `McpConnector` keeps using `say`.
- Every question gets exactly one result — `answered`, `asked` (answered with a question back) or `error`. There is no deadline on either side: a client that stops waiting simply ends its call, and the frontend lets go of the message. Attachments travel back with the answer.
- The frontend handles every client itself. It is a bridge with one MCP tool, `say`: it says what a client sends in the session as its own message, and sends the first reply to that message back to that client. No peer is added or removed per client; inside the remote session, every remote question comes from the frontend (`master`).
- Add opt-in credential delegation, following A2A's principle: the server declares the credentials its peers may use, a connector configured to delegate sends them out of band (MCP request metadata, HTTPS only), and the remote session keeps each one in memory only while that question is answered. A credential never enters message content or history. It rides on the message as metadata (`msg.credentials`), so the peer that answers uses that message's key for that reply, and one peer can work with a different key per message.
- Let answers carry a status (`Reply(..., status=ReplyStatus.ASKED | ReplyStatus.ERROR)`, a `ReplyStatus` `str` enum whose values `answered`, `asked` and `error` are also accepted, and are also the MCP result's statuses), kept on the answer's message (`ChatMessage.status`), so replies are relayed faithfully.
- In any session, a say that is not a reply, in a room where exactly one peer answers, is asked of that peer, and its reply comes back as a reply to the say; a peer that fails there replies `error`.
- Speak the modern MCP protocol (2026-07-28) only: no initialize handshake, and the client's name arrives with every request. MCP sampling is left out: it is deprecated in this protocol revision (SEP-2577), and credential delegation is how a remote peer borrows the asker's intelligence.
- Package the MCP pieces behind a new `chatinho[mcp]` extra; the core stays standard library only.
- Out of scope: routes through several sessions (multi-hop), choosing a remote peer from `McpConnector`, a peer router, sending API keys implicitly or in message content, and mirroring each remote peer as its own peer in the local roster.

## Capabilities

### New Capabilities
- `answer-details`: answer statuses on `Reply` and on the answer's message, and a say in a room with one peer that answers being asked of it.
- `credential-delegation`: credentials declared by the server, delegated out of band by the connector, carried on the message (`ChatMessage.credentials`), and alive only while that message is answered.
- `mcp-server`: `McpFrontend` — the MCP interface of a session, forwarding each client's question and routing the reply back, who answers a question (the only peer, or the first reply in the room), and the one-result guarantee.
- `mcp-connector`: `McpConnector` — naming, addressing from the local chat, sending questions, and bringing back answers and attachments.

### Modified Capabilities
<!-- None: attachments and message ids keep their contracts; answers that cross the link use them unchanged. -->

## Impact

- `src/chatinho/chat_session.py`: putting lent credentials on the message said; a say asked of the lone peer that answers; a peer whose `answer` raises fails the waiting `ask` or replies `error`.
- `src/chatinho/chat_message.py`: `ReplyStatus`, `Reply.status`, `ChatMessage.status`, `ChatMessage.credentials` and `Secret`.
- `src/chatinho/chat_hooks.py`: `say(..., credentials=…)`; `docs/SPEC.md` documents it.
- New `src/chatinho/frontends/mcp.py` (`McpFrontend`) and `src/chatinho/connectors/mcp.py` (`McpConnector`), exported lazily. `connectors/` and the new `frontends/` import each module on first use, so one battery never needs another's extra.
- `pyproject.toml`: an `mcp` extra (FastMCP, on the official `mcp` SDK), also added to `all` and `dev`; `uv.lock` updated.
- `README.md`, `CLAUDE.md`, an example under `examples/` for a headless MCP session.
- Security: an HTTP server lets clients put questions to every peer of the session; the HTTP transport requires a bearer token. With delegation, which is opt-in, the remote session holds a credential in memory for one question — so the docs recommend a sub-key with a spending limit or a short-lived token, never the main key.
