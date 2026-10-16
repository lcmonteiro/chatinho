# Proposal

## Why

`ChatMessage.to` holds two different things: who the speaker addressed, and which peer the session put the message to. When a say is routed to the room's lone answering peer, or a reply goes back to its author, the session writes that peer into `to`, so the say stops being a broadcast. A listener that only wants what was said to the room checks `msg.is_broadcast` (the docs say it must), and it silently stops hearing the user as soon as exactly one answering peer joins the room. Reproduced: an echo listener next to one answering bot never fires.

## What Changes

- **`to` is what the speaker chose, and nothing else.** A say the session routes keeps `to` unset, so it is still a broadcast and every listener that checks `is_broadcast` hears it.
- **New `ChatMessage.asked_of`**: the peer whose `answer` the session calls for the message, or None. It is `to` for an addressed say or an ask, the lone answering peer for a say routed to it, and the author for a reply routed back. An answer, an error reply, a command's invocation and its result are asked of nobody.
- **Who is asked comes from `asked_of`.** That also replaces the `answer=True` flag `_post` gained in #37: an answer is simply asked of nobody.
- **`AgentConnector` responds to the user's says only when it is not the one asked.** Otherwise a lone agent would answer the same message twice, once through `answer` and once through `listen`.
- **`Query(peer=)` matches `asked_of`**, so the questions a peer was asked stay in its memory.
- **`DatabaseBackend` archives `asked_of`**, in a new nullable column, so a restarted peer still remembers what it was asked. This schema is the baseline: an archive written before it is not upgraded.
- **BREAKING** for code that read `msg.to` to learn which peer was routed a say: it is `msg.asked_of` now. Nothing in the library or the examples does this, apart from the routing being changed here.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `answer-details`: the lone-answerer and reply rules ask a peer without addressing the say to it; a new requirement defines `asked_of`.
- `conversation-context`: `Query(peer=)` also matches what was asked of the peer; a new requirement says the archive keeps `asked_of`.
- `agent-connector`: "The user's says are responded to with a say" now names the says asked of the connector, not the ones addressed to it.

## Impact

- `src/chatinho/message.py`: the `asked_of` field.
- `src/chatinho/session.py`: `_say_for`, `_ask_for` and `_post` set and read `asked_of`; the `answer` flag on `_post` goes away.
- `src/chatinho/query.py`: the `peer` filter.
- `src/chatinho/connectors/agent.py`: the guard in `listen`.
- `src/chatinho/backends/database.py`: the column, and writing and reading it.
- Tests across `test_answer_details.py`, `test_message_delivery.py`, `test_context_query.py`, `test_agent_connector.py`, `test_database_backend.py`, `test_chat_frontend.py`, and the MCP tests that assert on `to`.
- Docs: `docs/SPEC.md` (the routing table, the lone-answerer and reply paragraphs, `HookListen`), CLAUDE.md's routing paragraph.
