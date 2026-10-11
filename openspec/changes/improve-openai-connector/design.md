# Design

## Context

`src/chatinho/connectors/openai.py` today:
- builds `openai.OpenAI` (synchronous) in `__init__`;
- calls `client.models.list()` in `initialize()` and raises on failure;
- sends only `msg.text` from `answer(msg, **kwargs)`.

The session calls `answer(msg)` with no keyword arguments, so `system_message` and `conversation_history` are dead code.

What the session already offers:
- **Grants:** `HookContext` grants `context(since=, start=, limit=)`, a list of `ChatMessage` that includes the message being answered. `HookPeers` grants `peers()`, a `{id: peer}` roster.
- **Credentials:** a message carries `credentials: Dict[str, Secret]`, lent per message (`credential-delegation`).
- **Failure modes:** when `answer` raises and nobody awaits, the session posts a generic error reply. Returning `Reply(..., status=ERROR)` lets the connector word it. `McpConnector` already does this for "could not reach".

See proposal.md for the motivation and specs/openai-connector for the required behaviour.

## Goals / Non-Goals

**Goals:**
- `answer` never blocks the event loop.
- The model sees the conversation, with roles mapped from who said what.
- A lent key is used for one message and dropped.
- Every failure ends as an `error` reply with no secret in it.

**Non-Goals:**
- Streaming partial replies into the chat.
- Tool or function calling.
- Sending attachments to the model. They never ride on a message, and reading one needs `locate` plus a fetch. That is a later change.
- Retries or backoff beyond what the OpenAI SDK does by default.

## Decisions

### `AsyncOpenAI`, one client per key
The connector keeps one `AsyncOpenAI(api_key=configured, base_url=base_url)` for its configured key, created lazily on first use. For a message with a lent key, it builds a short-lived `AsyncOpenAI(api_key=lent, base_url=base_url)` inside `answer` and closes it after the call, so the lent key leaves no client behind.

Alternatives considered:
- Passing the key per request through `extra_headers`. The SDK has no per-request `api_key`, and overriding `Authorization` by hand is brittle across compatible endpoints.
- Running the synchronous client in a thread with `asyncio.to_thread`. It keeps the old client but spends a thread per question. The SDK already ships an async client.

### History from `context()`, roles from identity
The connector declares `HookContext` and `HookPeers`. In `answer`, it:
1. Reads `self.context(limit=history + 1)` and drops the message being answered by id, so the question is sent once, last.
2. Finds its own id as the roster key whose peer `is self`.
3. Maps each remaining message: `frm == own id` becomes `assistant`; `frm == LOCAL` becomes `user` with the text as is; any other peer becomes `user` with `"<name>: <text>"`, where `name` comes from `name_of(peers()[frm])`. Messages from `TOOL`, or from a peer no longer in the roster, are labelled by their id. Messages with status `error` are skipped, since they are not conversation.

With `history=0` it neither reads the context nor the roster.

Alternatives considered:
- A per-connector transcript kept in memory. It duplicates the session's store and forgets everything recalled from the archive.
- Mapping other peers to `assistant` with a `name` field. Compatible endpoints handle `name` inconsistently, while a text prefix works everywhere.

### Errors are replies
`answer` catches `openai.OpenAIError` (and `httpx`/OS errors the SDK lets through) and returns `Reply("<name>: could not get an answer (<ErrorClass>)", status=ReplyStatus.ERROR)`. The class name is enough to tell authentication, rate limit and connection apart without echoing the SDK message, which can quote request details. A missing key is checked before any client is built: `Reply("<name>: no API key configured or lent as '<credential>'", status=ERROR)`.

The alternative was raising and letting the session post its generic error. That loses the "which connector, what kind" detail the user needs.

### `initialize()` does nothing on the network
The method is removed. The session already treats a missing `initialize` as nothing to do. Validation happens on the first question, as an error reply. This is what lets an MCP lab with no key of its own start.

### Constructor
`OpenAIConnector(name, api_key=None, *, model="gpt-4o", temperature=0.7, max_tokens=None, base_url=None, system=None, history=20, credential="llm")`.

`name` and `api_key` stay positional-compatible with today's `OpenAIConnector(name=..., api_key=...)`. The unused `**kwargs` and `self.config` are dropped. The default model stays `gpt-4o`, so existing callers see no change. Choosing a cheaper default is left to the examples.

## Risks / Trade-offs

- **[Context window overflow on long chats]** → `history` bounds it by message count. Token-aware trimming is out of scope, and a too-long request comes back as an error reply rather than a crash.
- **[A lent key lives in a client object for one call]** → The client is created and closed inside `answer`, never stored, and `Secret.reveal()` is called only to build it. Logs record the model and connector name, never the key.
- **[Behaviour change for callers relying on `initialize()` raising]** → It is noted as BREAKING in the proposal and the README. The package is 0.1.x.
- **[`context()` only reaches what `start()` recalled]** → This is a documented session limitation (see `_context`), and acceptable for chat memory.

## Migration Plan

This is a single PR. Callers that construct `OpenAIConnector(name=..., api_key=...)` need no change. Rollback is reverting the PR.
