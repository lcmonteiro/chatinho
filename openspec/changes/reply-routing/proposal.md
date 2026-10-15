# Proposal

## Why

Replies are routed by `to` alone, and an answer is addressed to whoever asked, so the session cannot tell a reply that *answers* from a reply that *asks*. Three things go wrong, each reproduced:

- **A follow-up goes unanswered.** In a chat with one assistant, the user selects its answer and replies to it. The reply has `reply_to` set and no `to`, so it is a broadcast; an assistant that only answers (`OpenAIConnector`, `McpConnector`) never hears it. In the terminal, tapping a message and typing is exactly this path.
- **Two answering peers trade answers until the depth limit.** One peer's say is asked of the other; the reply comes back addressed to the speaker, nothing is waiting on it, so it is handed to the speaker's `answer`, whose reply is handed back, and so on. One unprompted say cost eight `answer` calls — eight model calls with real connectors — before "nested deeper than 8" dropped it.
- **`McpFrontend` logs a false warning on every answer.** Its question is a `say(to=peer)`; the answer is addressed to `LOCAL`, delivered as a question to the frontend, and the frontend does not answer, so the session warns `'master' was asked but does not declare HookAnswer` — 18 times in `test_mcp_frontend.py` alone.

The root cause is the same: whether a message is put to a peer's `answer` is inferred from its shape instead of from what it is.

## What Changes

- **What `answer` returns is an answer, and is never asked of anyone.** The session still posts it addressed to the asker, with `reply_to` set, and everyone who listens hears it; but it never reaches anyone's `answer`. The same holds for the replies the session posts on a peer's behalf: the `error` reply when `answer` raises, and the "too many nested asks" reply. **BREAKING** for a peer that said something with `say(to=...)` and expected the reply in its own `answer`: it hears it through `listen` instead, as an asker of `ask` already does.
- **A say that replies goes back to whoever it replies to.** A say with `reply_to` set and no `to`, by a peer (not a command), is addressed to the author of the message it replies to, when that author is a peer other than the speaker and the frontend and declares `HookAnswer`. Otherwise it stays a broadcast, as today. An explicit `to` still wins.
- **The depth limit's "drop" clause** now applies to the replies that can still be put to a peer — a say replying to a reply — instead of to answers traded back and forth, which can no longer happen.

Out of scope: the interaction where auto-addressing a say to the lone answering peer hides it from listeners that check `msg.is_broadcast` (review item R4). It needs its own design decision.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `message-delivery`: "A reply that resolves an ask is heard, not answered" widens to every answer `answer` returned; "Nested asks are bounded" rewords what is dropped past the limit.
- `answer-details`: "A say in a room with one peer that answers is asked of it" no longer says a reply is always a broadcast; a new requirement says a reply is asked of the peer it replies to.

## Impact

- `src/chatinho/session.py`: `_say_for` (address a reply), `_post` (whether the message is put to its recipient), `_answered` and the error path in `_deliver` (post as answers).
- `src/chatinho/frontends/chat/__init__.py`: no code change expected; tapping a message and typing starts working.
- `src/chatinho/frontends/mcp.py`: no code change expected; the warning disappears.
- Tests: `tests/test_message_delivery.py::test_answers_traded_past_the_limit_are_dropped` and `tests/test_answer_details.py::test_a_reply_stays_a_broadcast` change meaning; new tests for the three reproduced failures.
- Docs: `docs/SPEC.md` (the routing table and "A room with one peer that answers"), CLAUDE.md's routing table.
