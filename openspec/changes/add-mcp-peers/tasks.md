# Tasks

## 1. Core: answers, peers and sampling

- [ ] 1.1 Add `status` to `Reply` (`answered` default, `asked`, `error`; anything else raises `ValueError`) and an `Answer(text, status, msg_id)` type in `chat_message.py`, exported from `chatinho`; verify unit tests for the default, explicit statuses and the invalid one pass
- [ ] 1.2 Add `detail=True` to the `ask` grant, resolving the pending future with an `Answer` (status from the answering `Reply`, `answered` for strings and for late replies via `say(reply_to=…)`); verify the default text-only `ask` tests still pass and new tests cover detail, statuses and `msg_id` locating an attachment
- [ ] 1.3 Add `ChatSession.remove_connector(peer_id)`: stop its drain task, drop its queue and entry, fail its pending asks with `PeerRemoved`, keep its messages, refuse `LOCAL` and unknown ids; verify tests for every `peer-lifecycle` scenario, plus one for adding a peer to a running session and calling `start()` again
- [ ] 1.4 Add `HookSample` (grant `sample`), `HookServeSample` (demands `serve_sample`), their protocols and `SamplingUnavailable`; the session routes `sample` to the frontend or raises; document both hooks in `docs/SPEC.md`; verify the `sampling` scenarios and `tests/test_architecture.py` pass

- [ ] 1.5 Add `HookCredential` (grant `credential`), `HookServeCredential` (demands `serve_credential`), their protocols, `CredentialUnavailable` and a `Secret` wrapper with a redacted `repr`; the session routes `credential` to the frontend or raises; document both hooks in `docs/SPEC.md`; verify the credential-hook scenarios and `tests/test_architecture.py` pass

## 2. Packaging

- [ ] 2.1 Add the `mcp` extra (`mcp>=2.3`) to `pyproject.toml`, include it in `all` and `dev`, refresh `uv.lock`, and register `McpServerFrontend` and `McpConnector` as lazy names with the extra in the missing-extra message; verify `import chatinho` works without `mcp` and the architecture extras test passes

## 3. MCP server frontend

- [ ] 3.1 Create `src/chatinho/mcp/` with the wire helpers (result building, asker validation, base64 attachments) and unit tests for them
- [ ] 3.2 Implement `McpServerFrontend` on the SDK's low-level `Server`: the five tools (`ask` with no peer name), `serve()` over stdio, `list_peers` excluding the frontend and proxies, `invoke`, `read_attachment`, statuses and the configurable default deadline (120 s); verify in-memory MCP tests for no broadcast tool, listing, answered, timeout within the deadline, a configured default deadline, and attachments returned
- [ ] 3.3 Add per-asker proxy peers named `<client>/<asker>` (asking, saying, listening for replies to their broadcasts, answering `error` when asked), removed when the connection ends; verify tests for an asker appearing by name, two clients as two askers, and proxies leaving on disconnect with history kept
- [ ] 3.4 Decide who answers: the only answering peer is asked directly; with several, the proxy says the question and the first reply to it is the result, or `error` at once when none of them declares `HookListen`; with none, `error`; a follow-up after `asked` goes to the same peer or is said as a reply to the `asked` answer; verify tests for only one peer, several peers, none listens, first reply wins, no peer, and both follow-up cases
- [ ] 3.5 Serve `HookServeSample` by relaying to the proxy's client through `create_message`, for direct and broadcast questions, raising `SamplingUnavailable` for messages without a client or when the client declines; verify tests with an in-memory client that samples and one that does not
- [ ] 3.6 Add credential delegation to the server: `credentials=` declared in `capabilities.experimental`, undeclared names dropped, credentials read from `_meta` and kept per question message id, served through `serve_credential` for direct and broadcast questions, popped in `finally` and on proxy removal; verify tests for declared in the handshake, undeclared ignored, gone after the answer, gone on timeout, and never in the context or store
- [ ] 3.7 Add the Streamable HTTP transport with a mandatory bearer token; verify a test that a request without the token is refused and one with it is served

## 4. MCP connector

- [ ] 4.1 Implement `McpConnector` (stdio `command` or HTTP `url` + `token`, `name`, optional `deadline`, `sample_with`): connect in `initialize()`, close in `shutdown()`, reconnect lazily, name from the server when not given, client name sent in the handshake; verify the naming scenarios over in-memory streams
- [ ] 4.2 Take `@name` addressing from local broadcasts and direct asks, ignore messages not addressed to it, and send the rest of the text with the asker's name; verify tests for addressed by name, not addressed, and the local asker appearing as `lab/me`
- [ ] 4.3 Reply exactly once per addressed message: text and attachments for `answered`, the remote question for `asked`, and short status messages for `error`, `timeout` and lost connections; verify tests for each
- [ ] 4.4 Serve sampling requests with `sample_with`, and decline without one; verify tests for the local model answering and nothing to sample with
- [ ] 4.5 Add `delegate=` to `McpConnector`: send only configured credentials the server declared, in `_meta`, calling callables per question; refuse non-`https` non-loopback URLs; never delegate a credential obtained through `credential`; verify tests for sent with the question, not declared not sent, plain HTTP refused, and token per question

## 5. End to end, docs and checks

- [ ] 5.1 Add an end-to-end test of two sessions over in-memory MCP: `@lab draw the login flow` from A reaches B's only peer and comes back with an attachment; with two peers in B, the question is said in B's room and the first reply returns; B's peer samples through A's `sample_with`; B names the asker `lab/me`
- [ ] 5.2 Add `examples/mcp_server.py` (a headless session served over stdio) and update `README.md` (extras table, an "MCP peers" section with addressing, who answers, sampling, opt-in credential delegation with its sub-key advice, and the token) and `CLAUDE.md`; verify the example runs and the README matches the API
- [ ] 5.3 Run `ruff check src tests examples`, `mypy src/chatinho`, `pytest -q` and `openspec validate --all --strict --no-interactive`; verify all pass
