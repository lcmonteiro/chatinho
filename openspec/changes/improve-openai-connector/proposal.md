# Proposal

## Why

`OpenAIConnector` is the one battery that makes chatinho talk to an LLM, and in its current form it is not usable for a real assistant:
- It calls the synchronous OpenAI client inside `async def answer`, so every question freezes the whole chat (terminal, MCP frontend, every other peer) until the model replies.
- It has no memory. The `conversation_history` and `system_message` keyword arguments are read from `**kwargs`, which the session never passes, so each question reaches the model alone.
- It ignores the credentials lent on a message (`credential-delegation`), so a session served over MCP cannot answer with the asker's key.
- It cannot reach any OpenAI-compatible endpoint other than OpenAI itself (Azure, OpenRouter, Ollama, LM Studio), because it takes no `base_url`.
- Its `initialize()` makes a blocking network call and raises without a valid key, so a chat whose only key arrives per message cannot even start.

The useful examples planned next (an assistant that remembers, two LLM roles in one chat, an MCP lab answering with a lent key) need all of this.

## What Changes

- The connector uses `AsyncOpenAI`, so waiting for the model never blocks the event loop.
- New constructor options:
  - `base_url`, for any OpenAI-compatible endpoint;
  - `system`, the system prompt for this peer;
  - `history`, how many earlier messages of the conversation to send (default 20, 0 for none);
  - `credential`, the name of the lent credential to answer with (default `llm`).
- The connector declares `HookContext` and `HookPeers`. It builds the model's messages from the conversation. Its own earlier replies become `assistant` turns. Everything else becomes `user` turns, prefixed with the speaker's name when the speaker is not the user.
- **BREAKING** `api_key` becomes optional. A key lent on the message wins over the configured one. With neither, the answer is an `error` reply that says which key is missing.
- **BREAKING** `initialize()` no longer calls the API. Configuration errors surface on the first question, as an error reply, instead of preventing the chat from starting.
- **BREAKING** The undocumented per-call `**kwargs` of `answer` (`model`, `temperature`, `max_tokens`, `system_message`, `conversation_history`) are removed. The session never passed them, and the new constructor options cover them.
- The connector gets its own tests, which it has never had, against a stubbed async client.

Not in scope: streaming partial replies, tool calls, sending attachments to the model, and other providers' SDKs.

## Capabilities

### New Capabilities
- `openai-connector`: how the OpenAI connector answers. It covers:
  - non-blocking calls;
  - endpoint, model and system prompt;
  - conversation memory;
  - which key it uses (lent or configured);
  - how failures are reported.

### Modified Capabilities

None. `credential-delegation` already allows a peer to use the credentials lent on a message. This change makes the OpenAI connector one such peer, without changing that requirement.

## Impact

- **Code:** `src/chatinho/connectors/openai.py` is rewritten.
- **Tests:** a new `tests/test_openai_connector.py`.
- **Docs:** `README.md` (the batteries example and a short connector section), `CLAUDE.md` and `docs/SPEC.md` where they describe the connector.
- **Dependencies:** none new. `openai>=1.0.0` already provides `AsyncOpenAI`.
- **Users:** `OpenAIConnector(name=..., api_key=...)` keeps working. Callers that relied on `initialize()` failing fast, or that passed per-call kwargs, must adapt.
