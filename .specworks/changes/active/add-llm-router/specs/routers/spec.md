# Spec Delta: routers

## ADDED Requirements

### Requirement: REQ-ROUTE-007 LLMRouter asks the model only when there is a choice

`LLMRouter` SHALL route as `SimpleRouter` does whenever `SimpleRouter`'s rules find a peer: a say that replies to another answering peer's message goes to that peer, and a say in a room with one answering peer goes to that peer, without asking the model. When those rules find no peer, it SHALL ask the model only if two or more peers answer, the speaker and the frontend not counted; with fewer, the say goes to nobody without asking the model.

#### Scenario: AC-ROUTE-007.1 A reply goes back to its author

- **GIVEN** a room with two answering peers, `gpt` and `weather`
- **WHEN** the user replies to `weather`'s answer
- **THEN** the reply is addressed to `weather` and the model was not asked

#### Scenario: AC-ROUTE-007.2 One answering peer

- **GIVEN** a room with one answering peer
- **WHEN** the user says something
- **THEN** that peer is asked and the model was not asked

#### Scenario: AC-ROUTE-007.3 Nobody answers

- **GIVEN** a room where no peer but the speaker answers
- **WHEN** a say is made
- **THEN** it goes to nobody and the model was not asked

#### Scenario: AC-ROUTE-007.4 A real choice

- **GIVEN** a room with two answering peers
- **WHEN** the user says something that replies to nothing
- **THEN** the model is asked once

### Requirement: REQ-ROUTE-008 The model picks a peer or everyone

When it asks the model, `LLMRouter` SHALL give it the name and description of every answering peer but the speaker and the frontend, the say's text, and the earlier messages its `memory` (a `Query`, by default the last 6 without failed replies) selects, the say itself not counted; a `memory` of `None` gives none. It SHALL read the model's answer as one peer name, ignoring case, a leading `@`, surrounding quotes and whitespace and trailing punctuation, and route the say to that peer; an answer of `everyone` MUST route the say to nobody, so it is a broadcast heard by all and answered by none.

#### Scenario: AC-ROUTE-008.1 The model names a peer

- **GIVEN** a room with two answering peers, `gpt` and `weather`
- **WHEN** the model answers `@Weather.`
- **THEN** the say is addressed to `weather`, which is asked it

#### Scenario: AC-ROUTE-008.2 Everyone

- **WHEN** the model answers `everyone`
- **THEN** the say is addressed to nobody, every listener hears it and no peer is asked

#### Scenario: AC-ROUTE-008.3 What the model is told

- **GIVEN** answering peers `gpt` and `weather` described `Forecasts by city`, and an earlier exchange
- **WHEN** the user says something and the model is asked
- **THEN** its prompt names `gpt` and `weather` with `Forecasts by city`, holds the say's text and the earlier messages, and names neither the speaker nor the frontend as a choice

#### Scenario: AC-ROUTE-008.4 Memory narrows what it is told

- **GIVEN** a router with `memory=Query().last(1)` and three earlier messages
- **WHEN** the model is asked
- **THEN** only the latest earlier message is in its prompt, besides the say

#### Scenario: AC-ROUTE-008.5 No memory

- **GIVEN** a router with `memory=None` and earlier messages
- **WHEN** the model is asked
- **THEN** none of the earlier messages is in its prompt

### Requirement: REQ-ROUTE-009 A failed choice is a broadcast

`LLMRouter` MUST route the say to nobody, and log a warning naming the reason but never a key or the say's text, when the model's answer names no answering peer, names a peer two answering peers share, or the request fails, raises, or takes longer than its `timeout` (10 seconds by default). The say MUST still be posted, and the chat MUST NOT wait longer than `timeout` for it.

#### Scenario: AC-ROUTE-009.1 An unknown name

- **WHEN** the model answers a name that is no answering peer
- **THEN** the say goes to nobody and a warning is logged

#### Scenario: AC-ROUTE-009.2 A shared name

- **GIVEN** two answering peers both named `bot`
- **WHEN** the model answers `bot`
- **THEN** the say goes to nobody and a warning is logged

#### Scenario: AC-ROUTE-009.3 The request fails

- **WHEN** the model's request raises an API error
- **THEN** the say is posted to nobody and a warning names the error's type

#### Scenario: AC-ROUTE-009.4 Too slow

- **GIVEN** a router with `timeout=0.1` and a model that takes 1 second
- **WHEN** a say is routed
- **THEN** it is posted to nobody within about 0.1 seconds, and a warning says the model timed out

#### Scenario: AC-ROUTE-009.5 No key

- **GIVEN** a router whose endpoint's key cannot be read, and no key lent
- **WHEN** a say is routed
- **THEN** it goes to nobody, and the warning names the key's reference but never a key

### Requirement: REQ-ROUTE-010 A lent key wins over the endpoint's

When a say carries a credential lent as `llm`, `LLMRouter` SHALL ask the model with that key instead of its endpoint's own, and MUST NOT keep it after the say is routed; with none lent it SHALL use its endpoint's key, read when first needed rather than when the router is built.

#### Scenario: AC-ROUTE-010.1 A lent key

- **GIVEN** a router with its own key, and a say lent the key `client-key` as `llm`
- **WHEN** the model is asked
- **THEN** the request is made with `client-key`

#### Scenario: AC-ROUTE-010.2 Its own key, read late

- **GIVEN** a router built from an endpoint whose key source is not yet readable
- **WHEN** the key becomes readable and a say is routed with none lent
- **THEN** the request is made with the endpoint's key

### Requirement: REQ-ROUTE-011 LLMRouter sits behind chatinho[openai]

`LLMRouter` SHALL be importable from `chatinho` and from `chatinho.routers`, and importing either package MUST NOT import `openai`. Reading `LLMRouter` without `openai` installed MUST raise `ImportError` naming `chatinho[openai]`.

#### Scenario: AC-ROUTE-011.1 The core does not need it

- **WHEN** `chatinho` and `chatinho.routers` are imported with `openai` blocked
- **THEN** both import, `SimpleRouter` among them, and `openai` was not imported

#### Scenario: AC-ROUTE-011.2 Without the extra

- **WHEN** `LLMRouter` is read off `chatinho` with `openai` blocked
- **THEN** it raises `ImportError` naming `chatinho[openai]`

#### Scenario: AC-ROUTE-011.3 Where it is imported from

- **WHEN** `LLMRouter` is read off `chatinho` and off `chatinho.routers`
- **THEN** both are the same class
