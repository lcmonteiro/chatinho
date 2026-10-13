## MODIFIED Requirements

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
