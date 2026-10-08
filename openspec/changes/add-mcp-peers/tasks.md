# Tasks

## 1. Core: answers and credentials

- [x] 1.1 Add `status` to `Reply` (`answered` default, `asked`, `error`; anything else raises `ValueError`) and to `ChatMessage` (`answered` default), set on the answer's message from its `Reply`; verify tests for the default, explicit statuses on the message, and the invalid one
- [x] 1.2 Make a say that is not a reply, not from a command, in a room where exactly one peer other than the speaker and the frontend answers, an ask of that peer; fail a waiting ask, or reply `error`, when a peer's `answer` raises; verify tests for one peer, several, a reply, the speaker and frontend not counting, a command's output, and a failing lone peer
- [x] 1.3 Add `ChatMessage.credentials` (keys by name as `Secret`, left out of `repr`) and `say(..., credentials=…)`, which puts the lender's very mapping on the message; document it in `docs/SPEC.md`; verify a key per message, clearing by the lender, and never shown
- [x] 1.4 Add `say(..., to=)`: an addressed say is asked of that peer without waiting, and a `to` that is not another peer raises `ValueError`; document it in `docs/SPEC.md`; verify tests for said to one peer and said to nobody

## 2. Packaging

- [x] 2.1 Add the `mcp` extra (`fastmcp>=4.0`) to `pyproject.toml`, include it in `all` and `dev`, refresh `uv.lock`, and register `McpFrontend` and `McpConnector` as lazy names with the extra in the missing-extra message; verify `import chatinho` works without `mcp` and the architecture extras test passes

## 3. MCP server frontend

- [x] 3.1 Add the result helpers to each end — building the result in `McpFrontend` (with asker validation and base64 attachments) and reading it back into a `Reply` in `McpConnector` — and unit tests for them
- [x] 3.2 Implement `McpFrontend` (named `master` unless given a name, used as the server's name) as a `FastMCP` server, modern protocol (2026-07-28): the tool `say` (no peer name), `serve()` over Streamable HTTP with a required token, and statuses; verify in-process FastMCP `Client` tests for the default name `master`, the tool `say`, answered, and attachments returned
- [x] 3.3 Have the frontend bridge every client: say each message as its own, map the said id to that client's call, send the first reply back on that call, keep follow-ups per `(client, asker)`, and answer `error` when a peer asks it; no peer is added or removed per client; verify tests for the reply going back to its client, two clients at once, and a peer asking the frontend
- [x] 3.4 Decide who answers: the only answering peer is asked the say by the session; with several, it is said to the room and the first reply to it is the result, or `error` at once when none of them declares `HookListen`; with none, `error`; a follow-up goes to the same peer, or in the room is said as a reply to the asker's last answer there; verify tests for only one peer, several peers, none listens, first reply wins, no peer, and both follow-up cases
- [x] 3.5 Add credential delegation to the server: `credentials=` declared in the `server/discover` result as the `chatinho/credentials` extension, undeclared names dropped, credentials read from the call's `_meta`, said with the message as `credentials=`, and cleared in `finally`; verify tests for declared at discovery, undeclared ignored, a key per message, gone after the answer, gone when the client gives up, and never in the context or store
- [x] 3.6 Add the Streamable HTTP transport with a mandatory bearer token; verify a test that a request without the token is refused and one with it is served
- [x] 3.7 Add the rest of the terminal's tools: `ask(peer, text)` through an addressed say, `peers()`, `tools()` and `run(name, args?)` through `invoke`; verify tests for the tools listed, asked by name, a question back, a failing peer, who cannot answer (unknown, not answering, ambiguous, the frontend), lent credentials, peers, tools, run and an unknown tool

## 4. MCP connector

- [x] 4.1 Implement `McpConnector` (HTTP `url` + `token`, or an in-process `server`, `name`): open a `fastmcp.Client` per question (`async with client:`), with no link left open between questions, name from the server when not given, client name sent with every request; verify the naming scenarios against an in-process server
- [x] 4.2 React only to asks (no `HookListen`): drop an optional leading `@name`, and send the rest of the text with the asker's name; verify tests for asked directly, said to the room not taken, and the asker's name reaching the frontend
- [x] 4.3 Answer exactly once per question: text and attachments for `answered`, the remote question for `asked`, and short status messages for `error` and lost connections; verify tests for each
- [x] 4.4 Add `delegate=` to `McpConnector`: discover the server's declared credentials, send only configured ones it declared, in `_meta`, calling callables per question; refuse non-`https` non-loopback URLs; never delegate a credential found on a message; verify tests for sent with the question, not declared not sent, plain HTTP refused, and token per question

## 5. End to end, docs and checks

- [x] 5.1 Add an end-to-end test of two sessions over the modern protocol, in-process: `@lab draw the login flow` from A reaches B's only peer and comes back with an attachment; with two peers in B, the question is said in B's room and the first reply returns; B's peer reads a credential A delegates; B's peers are asked by its frontend
- [x] 5.2 Add `examples/mcp_server.py` (a headless session served over HTTP with a token) and update `README.md` (extras table, an "MCP peers" section with addressing, who answers, opt-in credential delegation with its sub-key advice, and the token) and `CLAUDE.md`; verify the example runs and the README matches the API
- [x] 5.3 Run `ruff check src tests examples`, `mypy src/chatinho`, `pytest -q` and `openspec validate --all --strict --no-interactive`; verify all pass
