# models

## Purpose

The one model every component of chatinho calls: an OpenAI-compatible endpoint,
its own key read late, a key per call for a key a message lends, and the same
model as a LangChain chat model.

## Requirements

### Requirement: REQ-MODEL-001 A call is made with its own key or the endpoint's

`EndpointModel` SHALL make one chat completion per `complete(messages, api_key=None, **params)`,
asking the endpoint's model (`gpt-4o` when the endpoint names none) with
`params` passed through. A call given `api_key`, a `Secret`, MUST reach the
model with that key, by a client built for that call and closed when it
returns; a call given none MUST use the endpoint's own key, read when the call
needs it and never when the model is built. With neither, or when the own key's
source cannot yield one, the call MUST raise `KeyUnavailable` without a request.
Headers the model was built with MUST be sent with every request, whichever key
it carries. No key MUST appear in the model's `repr`.

#### Scenario: AC-MODEL-001.1 A key on the call, then its own

- **GIVEN** a model whose endpoint's key is `sk-own`
- **WHEN** it completes once with `api_key=Secret("sk-call")`, then once with none
- **THEN** the first request carries `sk-call`, the second `sk-own`, and the first call's client is closed

#### Scenario: AC-MODEL-001.2 No key at all

- **GIVEN** a model whose endpoint has no key
- **WHEN** it completes with no `api_key`
- **THEN** it raises `KeyUnavailable` and no client is built

#### Scenario: AC-MODEL-001.3 A source that cannot read

- **GIVEN** a model whose key is `Env("MODEL_TEST_KEY")`, unset
- **WHEN** it completes with no `api_key`
- **THEN** it raises `KeyUnavailable` naming `MODEL_TEST_KEY`, and no request is made

#### Scenario: AC-MODEL-001.4 Headers with either key

- **GIVEN** a model built with `headers={"Editor-Version": "v1"}`
- **WHEN** it completes with its own key and with `api_key=Secret("sk-call")`
- **THEN** both clients are given `Editor-Version: v1`

#### Scenario: AC-MODEL-001.5 Read late, never shown

- **WHEN** a model is built on an endpoint whose key is a function returning `sk-secret`, then completes
- **THEN** the function was not called when it was built, was called for the request, and `sk-secret` is not in the model's `repr`

### Requirement: REQ-MODEL-002 Its own key keeps one client, following the key

The model SHALL build one client for its own key and share it between calls
made at once. When the key its source yields changes, the next call MUST use a
new client, and the old one MUST be closed only once no call is using it.
`close()` MUST close the client it kept, and a model that never built one MUST
close without error.

#### Scenario: AC-MODEL-002.1 Calls at once share one client

- **WHEN** the model completes three times at once with its own key
- **THEN** each call gets its answer and one client was built

#### Scenario: AC-MODEL-002.2 A rotated-out client

- **WHEN** the key changes while a call is still being answered with the old one
- **THEN** the next call uses a new client, and the old one stays open until that call returns and is closed after

#### Scenario: AC-MODEL-002.3 Closed

- **WHEN** a model that completed once is closed, and a model that never completed is closed
- **THEN** the first's client is closed and closing the second raises nothing

### Requirement: REQ-MODEL-003 The model as a LangChain chat model takes a key per call

`EndpointModel.chat_model()` SHALL return a chat model callable as any
LangChain chat model is, asynchronously, that takes an optional `api_key`, a
`Secret`, on each call. A call given one MUST reach the model with that key; a
call given none MUST use the key the run's configuration carries as `api_key`
under `configurable`, and with neither, the endpoint's own key, read when the
model is called. The parameter wins over the configuration. Tools bound to the
model MUST keep this behaviour. The model MUST NOT keep a key it was given after
the call returns, and a key MUST NOT appear in its `repr`. It is asynchronous
only: a synchronous call MUST raise `NotImplementedError` without reaching the
model.

#### Scenario: AC-MODEL-003.1 A key on the call

- **GIVEN** the chat model of an endpoint whose own key is `sk-own`
- **WHEN** it is called with `api_key=Secret("sk-call")`, then with no key
- **THEN** the first request carries `sk-call` and the second `sk-own`

#### Scenario: AC-MODEL-003.2 A key in the run's configuration

- **GIVEN** the chat model of an endpoint whose own key is `sk-own`
- **WHEN** it is called with `configurable={"api_key": Secret("sk-config")}`, then with that and `api_key=Secret("sk-call")`
- **THEN** the first request carries `sk-config` and the second `sk-call`

#### Scenario: AC-MODEL-003.3 Bound tools keep it

- **WHEN** tools are bound to the chat model and the result is called with `api_key=Secret("sk-call")`
- **THEN** the request carries `sk-call` and the tools

#### Scenario: AC-MODEL-003.4 Nothing kept

- **WHEN** the chat model has been called with `api_key=Secret("sk-call")`
- **THEN** `sk-call` is in neither its `repr` nor any of its attributes

#### Scenario: AC-MODEL-003.5 Asynchronous only

- **WHEN** the chat model is called synchronously
- **THEN** it raises `NotImplementedError` and no request is made

### Requirement: REQ-MODEL-004 The key a message lends

`lent_key(msg, credential)` SHALL return the `Secret` lent on `msg` under the
name `credential`, and None when it lends none under that name.

#### Scenario: AC-MODEL-004.1 Lent, and not

- **WHEN** a message lends `llm` = `sk-a` and `other` = `sk-b`
- **THEN** `lent_key(msg, "llm")` reveals `sk-a`, and `lent_key(msg, "missing")` and `lent_key` of a message lending nothing are None

### Requirement: REQ-MODEL-005 LangChain only for the LangChain face

Importing the model kit SHALL need `openai` and nothing of LangChain; only
`chat_model()` MUST import it, and without `langchain-openai` it MUST raise an
`ImportError` naming `chatinho[langchain]`.

#### Scenario: AC-MODEL-005.1 Without LangChain

- **GIVEN** a Python in which `langchain_core` and `langchain_openai` cannot be imported
- **WHEN** the model kit is imported, a model completes, and `chat_model()` is called
- **THEN** the import and the completion succeed, and `chat_model()` raises `ImportError` naming `chatinho[langchain]`

### Requirement: REQ-MODEL-006 Every component calls a model through it

No module of chatinho outside the model kit SHALL build an OpenAI client or a
LangChain OpenAI chat model: `OpenAIConnector`, `LLMRouter` and `AgentPeer`
MUST each call their model through an `EndpointModel`.

#### Scenario: AC-MODEL-006.1 One door

- **WHEN** every module under `src/chatinho` is parsed
- **THEN** only modules of `support/kits/model` import `AsyncOpenAI`, `OpenAI` or `ChatOpenAI`
