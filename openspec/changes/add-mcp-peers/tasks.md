# Tasks

## 1. Core: answers, peers and sampling

- [ ] 1.1 Add `status` to `Reply` (`answered` default, `asked`, `error`; anything else raises `ValueError`) and an `Answer(text, status, msg_id)` type in `chat_message.py`, exported from `chatinho`; verify unit tests for the default, explicit statuses and the invalid one pass
- [ ] 1.2 Add `detail=True` to the `ask` grant, resolving the pending future with an `Answer` (status from the answering `Reply`, `answered` for strings and for late replies via `say(reply_to=…)`); verify the default text-only `ask` tests still pass and new tests cover detail, statuses and `msg_id` locating an attachment
- [ ] 1.3 Add `ChatSession.remove_connector(peer_id)`: stop its drain task, drop its queue and entry, fail its pending asks with `PeerRemoved`, keep its messages, refuse `LOCAL` and unknown ids; verify tests for every `peer-lifecycle` scenario, plus one for adding a peer to a running session and calling `start()` again
- [ ] 1.4 Add `HookSample` (grant `sample`), `HookServeSample` (demands `serve_sample`), their protocols and `SamplingUnavailable`; the session routes `sample` to the frontend or raises; document both hooks in `docs/SPEC.md`; verify the `sampling` scenarios and `tests/test_architecture.py` pass

## 2. Packaging

- [ ] 2.1 Add the `mcp` extra (`mcp>=2.3`) to `pyproject.toml`, include it in `all` and `dev`, refresh `uv.lock`, and register `McpServerFrontend` and `McpConnector` as lazy names with the extra in the missing-extra message; verify `import chatinho` works without `mcp` and the architecture extras test passes

## 3. MCP server frontend

- [ ] 3.1 Create `src/chatinho/mcp/` with the wire helpers (result building, route and asker validation, base64 attachments) and unit tests for them
- [ ] 3.2 Implement `McpServerFrontend` on the SDK's low-level `Server`: the five tools, `serve()` over stdio, `ask` with proxies, the configurable default deadline (120 s), statuses and `hop`, `list_peers` excluding the frontend and proxies, `invoke`, `read_attachment`; verify in-memory MCP tests for directed-only tools, listing, answered, unknown peer, timeout within the deadline, a configured default deadline, `asked` continuing the conversation, and attachments returned
- [ ] 3.3 Add per-asker proxy peers named by client name and asker path, removed when the connection ends; verify tests for an asker appearing by name, two clients as two askers, and proxies leaving on disconnect with history kept
- [ ] 3.4 Add multi-hop forwarding (`forward` on connectors), visited session ids, hop limit 8 and `hop` naming; verify tests for two hops, loop refused, too many hops, and errors naming the hop
- [ ] 3.5 Serve `HookServeSample` by relaying to the proxy's client through `create_message`, raising `SamplingUnavailable` for messages without a client or when the client declines; verify tests with an in-memory client that samples and one that does not
- [ ] 3.6 Add the Streamable HTTP transport with a mandatory bearer token; verify a test that a request without the token is refused and one with it is served

## 4. MCP connector

- [ ] 4.1 Implement `McpConnector` (stdio `command` or HTTP `url` + `token`, `name`, default `peer`, optional `deadline`, `sample_with`): connect in `initialize()`, close in `shutdown()`, reconnect lazily, name from the server when not given, client name sent in the handshake; verify the naming scenarios over in-memory streams
- [ ] 4.2 Parse `@name(/seg)*` addressing from local broadcasts and direct asks, ignore messages not addressed to it, use the default peer, and send the asker path; verify tests for addressed by route, not addressed, default peer, local asker `lab/me` and forwarded asker `office/lab/me`
- [ ] 4.3 Reply exactly once per addressed message: text and attachments for `answered`, the remote question for `asked`, and short status messages naming the hop for `error`, `timeout` and lost connections; verify tests for each
- [ ] 4.4 Serve sampling requests with `sample_with` for local questions, relay through `sample` for forwarded ones, and decline otherwise; verify tests for local model, relayed toward the origin across two hops, and nothing to sample with

## 5. End to end, docs and checks

- [ ] 5.1 Add an end-to-end test of three sessions (A → B → C) over in-memory MCP: `@lab/office/weather` gets C's answer with an attachment in A, C's peer samples through A's `sample_with`, and B and C name the asker `lab/me` and `office/lab/me`
- [ ] 5.2 Add `examples/mcp_server.py` (a headless session served over stdio) and update `README.md` (extras table, an "MCP peers" section with addressing, sampling and the token) and `CLAUDE.md`; verify the example runs and the README matches the API
- [ ] 5.3 Run `ruff check src tests examples`, `mypy src/chatinho`, `pytest -q` and `openspec validate --all --strict --no-interactive`; verify all pass
