## MODIFIED Requirements

### Requirement: Endpoint, model and system prompt are configurable
The connector SHALL accept a `base_url` for any OpenAI-compatible endpoint, a `model`, a `temperature`, an optional `max_tokens` and an optional `system` prompt. It SHALL also accept an `endpoint`, which supplies the URL, model and key when those arguments are not given. An explicit `base_url`, `model` or `api_key` argument MUST win over the endpoint's. With neither, the model MUST be `gpt-4o` and the URL OpenAI's own. When `system` is given, it MUST be the first message sent to the model. When a URL is given, by argument or endpoint, every request MUST go to it.

#### Scenario: A system prompt leads
- **WHEN** a connector created with `system="You review code."` is asked something
- **THEN** the first message sent to the model is a `system` message with that text

#### Scenario: Another endpoint
- **WHEN** a connector is created with `base_url="http://localhost:11434/v1"`
- **THEN** its requests go to that endpoint

#### Scenario: From an endpoint
- **WHEN** a connector is created with an endpoint for `http://localhost:11434/v1`, model `qwen`, and a key source
- **THEN** its requests go to that URL with model `qwen` and the key the source yields

#### Scenario: An explicit model wins
- **WHEN** a connector is created with that endpoint and `model="llama"`
- **THEN** its requests use model `llama` and the endpoint's URL and key

### Requirement: A lent key wins over the configured one
The connector SHALL answer with the credential lent on the message under its `credential` name (default `llm`) when there is one. Otherwise it SHALL answer with its configured key:
- the `api_key` argument, which may be a string, a key source or a function returning a string;
- else the endpoint's key source.

The configured key MUST be read when a question needs it, not when the connector is created, and MUST be held only as a `Secret`. A lent key MUST be used for that message only, and MUST NOT be kept, logged, or reused for another message.

The connector MUST answer with an `error` reply, without calling the model:
- when it has neither a lent nor a configured key, naming the missing key;
- when the configured source cannot yield a key, carrying the source's error, which names the reference and never a value.

#### Scenario: Answered with the asker's key
- **WHEN** a connector configured with `api_key="sk-own"` answers a message that was lent `llm` = `sk-lent`
- **THEN** the request for that message uses `sk-lent`, and the next message without a lent key uses `sk-own`

#### Scenario: No key at all
- **WHEN** a connector with no `api_key` and no endpoint answers a message lent nothing
- **THEN** it answers with an `error` reply that says no key was configured or lent, and the model is not called

#### Scenario: A source that cannot read
- **WHEN** a connector whose `api_key` is `Env("OPENAI_API_KEY")` answers while that variable is unset
- **THEN** it answers with an `error` reply naming `OPENAI_API_KEY`, and the model is not called

#### Scenario: A rotated key is used
- **WHEN** a connector's key source is a file, it answers once, the file is rewritten with a new key, and it answers again
- **THEN** the second request uses the new key

#### Scenario: The key is not shown
- **WHEN** a connector configured with `api_key="sk-own"` is printed, or its attributes are listed
- **THEN** `sk-own` appears nowhere
