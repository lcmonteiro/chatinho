# openai-connector Specification

## Purpose

Defines how `OpenAIConnector` answers: through any OpenAI-compatible endpoint, without blocking the chat, remembering the part of the conversation its memory query selects, and answering with the key lent on the message when there is one.

## Requirements

### Requirement: Answering never blocks the chat
`OpenAIConnector` SHALL wait for the model without blocking the session's event loop, so other peers and the frontend keep working while it waits. It MUST answer with a `Reply` holding the model's text.

#### Scenario: The chat keeps moving while the model thinks
- **WHEN** the connector is asked a question and the model takes a while to reply
- **THEN** another peer's message is delivered before the model's reply arrives

#### Scenario: The model's text is the answer
- **WHEN** the model replies "Sunny"
- **THEN** the connector answers with a `Reply` whose text is "Sunny" and whose status is `answered`

### Requirement: Endpoint, model and system prompt are configurable
The connector SHALL take where to ask, which model and which key as one `endpoint` (an `Endpoint`), rather than as separate arguments. It SHALL also accept a `temperature`, an optional `max_tokens` and an optional `system` prompt.
- The endpoint's URL may be any OpenAI-compatible endpoint. When it is set, every request MUST go to it; when it is unset, requests go to OpenAI itself.
- The endpoint's model MUST be the model asked; when it is unset, or no endpoint is given, the model MUST be `gpt-4o`.
- When `system` is given, it MUST be the first message sent to the model.

#### Scenario: A system prompt leads
- **WHEN** a connector created with `system="You review code."` is asked something
- **THEN** the first message sent to the model is a `system` message with that text

#### Scenario: Another endpoint
- **WHEN** a connector is created with an endpoint for `http://localhost:11434/v1`, model `qwen`, and a key
- **THEN** its requests go to that URL with model `qwen` and that key

#### Scenario: Another model on the same endpoint
- **WHEN** a connector is created with that endpoint's `with_model("llama")`
- **THEN** its requests use model `llama` and the endpoint's URL and key

#### Scenario: No endpoint
- **WHEN** a connector is created without an endpoint
- **THEN** it asks OpenAI itself, with model `gpt-4o`

### Requirement: The conversation is remembered
The connector SHALL take a `memory` query (a `Query`, default `Query(peer=SELF, errors=False).last(20)`) and send the model the messages `context()` returns for it, oldest first, before the question. The default covers what passed between it and anyone, without error replies. The connector's own earlier replies MUST be sent as `assistant` messages. Every other message MUST be sent as a `user` message. A message from a peer other than the user MUST be prefixed with that peer's name, as `name: text`. The question itself MUST be sent once, last, and never counts against the query's limit. With `memory=None`, only the question (after any system prompt) MUST be sent.

#### Scenario: A follow-up question
- **WHEN** the user said "My name is Ana", the connector answered "Hi Ana", and the user now asks "What is my name?"
- **THEN** the model receives `user: My name is Ana`, `assistant: Hi Ana`, `user: What is my name?`, in that order

#### Scenario: Another peer in the room
- **WHEN** a connector created with `memory=Query(errors=False)` is asked to review, after a peer named `coder` said "def f(): pass" to everyone
- **THEN** the model receives that message as a `user` message reading `coder: def f(): pass`

#### Scenario: Only its own exchanges by default
- **WHEN** a connector with the default memory is asked something, after two other peers talked to each other
- **THEN** their exchange is not sent to the model

#### Scenario: No memory
- **WHEN** a connector created with `memory=None` is asked a question after a long conversation
- **THEN** the model receives only the question

### Requirement: A lent key wins over the configured one
The connector SHALL answer with the credential lent on the message under its `credential` name (default `llm`) when there is one. Otherwise it SHALL answer with its endpoint's key, which may be given as a string, a key source or a function returning a string.

The configured key MUST be read when a question needs it, not when the connector is created, and MUST be held only as a `Secret`. A lent key MUST be used for that message only, and MUST NOT be kept, logged, or reused for another message.

The connector MUST answer with an `error` reply, without calling the model:
- when it has neither a lent key nor an endpoint key, naming the missing key;
- when the endpoint's key source cannot yield a key, carrying the source's error, which names the reference and never a value.

#### Scenario: Answered with the asker's key
- **WHEN** a connector whose endpoint key is `sk-own` answers a message that was lent `llm` = `sk-lent`
- **THEN** the request for that message uses `sk-lent`, and the next message without a lent key uses `sk-own`

#### Scenario: No key at all
- **WHEN** a connector whose endpoint has no key answers a message lent nothing
- **THEN** it answers with an `error` reply that says no key was configured or lent, and the model is not called

#### Scenario: A source that cannot read
- **WHEN** a connector whose endpoint key is `Env("OPENAI_API_KEY")` answers while that variable is unset
- **THEN** it answers with an `error` reply naming `OPENAI_API_KEY`, and the model is not called

#### Scenario: A rotated key is used
- **WHEN** a connector's endpoint key is a file, it answers once, the file is rewritten with a new key, and it answers again
- **THEN** the second request uses the new key

#### Scenario: The key is not shown
- **WHEN** a connector whose endpoint key is `sk-own` is printed, or its attributes are listed
- **THEN** `sk-own` appears nowhere

### Requirement: Failures are answers, and starting needs no network
`initialize()` SHALL NOT call the model's API, so a chat starts even when its key arrives only with each message. A failed request (network, authentication, rate limit) MUST become an `error` reply that names the connector and the kind of failure. It MUST NOT include any key.

#### Scenario: Starting without a key
- **WHEN** a session with a connector that has no `api_key` starts
- **THEN** it starts, and no request is made

#### Scenario: The endpoint refuses
- **WHEN** the endpoint answers with an authentication error
- **THEN** the connector answers with an `error` reply naming itself and the authentication failure, and the key appears nowhere in it

### Requirement: Its client closes with the chat
The OpenAI connector SHALL close the client it keeps for its own key when the chat closes. A connector that never built a client MUST close without error.

#### Scenario: Asked, then closed
- **WHEN** an OpenAI connector answers a question with its own key, and the chat is closed
- **THEN** the client it built for that key is closed

#### Scenario: Never asked
- **WHEN** an OpenAI connector is never asked anything, and the chat is closed
- **THEN** closing raises nothing
