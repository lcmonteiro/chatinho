# Proposal

## Why

A message carries two fields for one question. `to` is what the speaker chose, and `asked_of` is whose `answer` the session calls. They were split so that a say routed to the room's lone answering peer stayed a broadcast. The cost is that every reader has to know which of the two to look at: `McpFrontend`, `AgentConnector`, `Query(peer=)` and the archive all read `asked_of`, while listeners filter on `is_broadcast`. The routing rule that fills `asked_of` is also fixed inside `ChatSession._answerer_of`, so a chat that wants a model to pick who answers has nowhere to put that decision.

This change makes `to` the only answer to "who answers this". When the speaker leaves `to` unset, a **router** fills it in. The router can be swapped: rule-based by default, or backed by an LLM.

## What Changes

- **New: a router decides `to` for an unaddressed say.** A router is a plain class that declares the new `HookRoute`, which demands `async route(msg) -> Optional[int]`. The router is what `ChatSession(router=…)` is given. Like a command, it is not a peer: it has no id and is in nobody's roster, but it is granted what it declares. A session given no router routes nothing.
- **New: `SimpleRouter`, the builders' default.** `build_chat_session` and `build_mcp_session` give it unless passed a `router=`. It holds no state and imports only the standard library. It keeps today's two rules, now writing them into `to`:
  - A say that replies to a message goes to that message's author, when the author is a peer that answers and is neither the speaker nor the frontend.
  - Any other say goes to the one peer that answers other than the speaker and the frontend. With none, or with more than one, `to` stays `None` and nobody answers.
- The session consults the router only for a say with `to` unset, said by a peer (not by `TOOL`), that is not an answer. A router result that is not a peer that answers, other than the speaker, is ignored with a warning. A router that raises is logged, and `to` stays `None`.
- **BREAKING: an answer is addressed to nobody.** What `answer` returns, the `error` and "too many nested asks" replies the session posts, and a say replying to a message that was put to the speaker are all posted with `to = None`. They used to carry `to = asker`. Without `asked_of`, `to` set on an answer would put the answer to its asker's `answer`, and a user following up on an answer would look exactly like an answer.
- **BREAKING: `ChatMessage.asked_of` is removed.** Gone with it: the `asked_of` column in `DatabaseBackend` and the `asked_of` match in `Query(peer=)`. An `ask` is resolved by a reply from the peer the question is addressed to (`to`). `McpFrontend` reads the question's `to`.
- **BREAKING: `ChatMessage.is_broadcast` is removed.** Its readers, `examples/hooks.py`'s echo connector and `AgentConnector.listen`, check `msg.to is None` directly. `to is None` now means "owed by nobody", not "said to the room".
- **BREAKING: a routed say has `to` set.** In a room with one answering peer, the user's say now carries `to = that peer`. A listener that responds only to says owed by nobody therefore stays quiet there, which is what `AgentConnector` already does by hand today.
- The hook count goes from fourteen to fifteen. `docs/SPEC.md`, `examples/hooks.py`, `CLAUDE.md` and the public API (`HookRoute`, `SimpleRouter`) are updated to match.

## Capabilities

### New Capabilities
- `message-routing`: the router: `HookRoute`, who the router is (what `router=` is given, not a peer; `SimpleRouter` in the builders), when the session consults it, how its result is checked, and `SimpleRouter`'s two rules.

### Modified Capabilities
- `answer-details`: the lone-answering-peer and reply-routing requirements move to the router and set `to`. The requirement that a message carries `asked_of` is removed, and an answer is addressed to nobody.
- `message-delivery`: whether a peer's `answer` is called, and which reply resolves a waiting `ask`, are decided by `to`. Answers are posted with `to` unset.
- `conversation-context`: `Query(peer=)` no longer matches `asked_of`, and the archive no longer keeps it.
- `agent-connector`: "the user's says are responded to with a say" is decided by `to is None` instead of `is_broadcast` and `asked_of`.

## Impact

- **Code:** `session.py` (`_answerer_of` replaced by the router call, `_post` audience and resolution, `_answered` and the error replies), `message.py` (remove `asked_of`, `is_broadcast`), `hooks.py` (`HookRoute`), new `routers/` package (`SimpleRouter`), `query.py`, `backends/database.py`, `frontends/mcp.py`, `connectors/agent.py`, `__init__.py`.
- **Docs and examples:** `docs/SPEC.md` (a fifteenth hook, the message table), `CLAUDE.md`, `examples/hooks.py` (echo filter, a router example).
- **Tests:** `test_answer_details.py`, `test_message_delivery.py`, `test_context_query.py`, `test_database_backend.py`, `test_mcp_*`, `test_agent_connector.py`, `test_architecture.py` (the SPEC table check), `test_package_layout.py` (export count).
- **Archives:** an archive written before this change keeps its `asked_of` column, which is now ignored, and its answers keep `to = asker`. Nothing is migrated, as with `status` and `asked_of` before.
- **Dependencies:** none. The router machinery and `SimpleRouter` are stdlib-only core.
