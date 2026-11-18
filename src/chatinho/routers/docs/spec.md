# routers

## Purpose

Who answers a say that names nobody: the router a session is given decides, and the default one, `SimpleRouter`, keeps a reply with its author and anything else with the room's lone answering peer. It has no living spec yet; this records the behaviour it already has.

## Requirements

### Requirement: REQ-ROUTE-001 A router decides who an unaddressed say is for

When a peer says something with no `to`, the session SHALL hand the say to its router and use what the router returns as the say's `to` before anyone hears it; `None` leaves it addressed to nobody. The router MUST NOT be consulted for a say that names its peer, for what a command writes, for a command's invocation or its answer, or for a late answer to something put to its speaker.

#### Scenario: AC-ROUTE-001.1 Routed to one peer

- **WHEN** a router that picks `bot` is given a say
- **THEN** the say is addressed to `bot`, only `bot` is asked, and the router was consulted once

#### Scenario: AC-ROUTE-001.2 Routed to nobody

- **WHEN** the router returns `None`
- **THEN** the say is addressed to nobody and nobody is asked

#### Scenario: AC-ROUTE-001.3 An addressed say

- **WHEN** a say names its peer
- **THEN** the router is not consulted and only that peer is asked

#### Scenario: AC-ROUTE-001.4 A command's output

- **WHEN** a command is run
- **THEN** the router is not consulted

#### Scenario: AC-ROUTE-001.5 What a command writes

- **WHEN** a command says something while it runs
- **THEN** nobody is asked it and it is addressed to nobody

#### Scenario: AC-ROUTE-001.6 A command's answer

- **WHEN** a command is run
- **THEN** its invocation is addressed to `TOOL` and its answer to nobody

#### Scenario: AC-ROUTE-001.7 A late answer

- **WHEN** a peer answers a question later, with a say replying to it
- **THEN** the asker gets the answer and the router is not consulted

### Requirement: REQ-ROUTE-002 The router is a role, not a peer

The session's router SHALL be what it was given as `router`, and MUST declare `HookRoute`, or the session raises `TypeError`. It is in no roster, has no id, may read the room through the grants it declares, and is started and shut down with the chat. A connector that declares `HookRoute` is not the router, and a session given no router routes nothing.

#### Scenario: AC-ROUTE-002.1 A connector is not the router

- **WHEN** a connector declares `HookRoute` and the session has no router
- **THEN** a say is addressed to nobody and the connector is not consulted

#### Scenario: AC-ROUTE-002.2 It reads the room

- **WHEN** a router that declares `HookPeers` picks the peer that answers
- **THEN** it is in no roster, has no id, and the say goes to that peer

#### Scenario: AC-ROUTE-002.3 Started and stopped with the chat

- **WHEN** a session with a router that has `initialize` and `shutdown` starts and closes
- **THEN** both ran, in that order

#### Scenario: AC-ROUTE-002.4 It must declare HookRoute

- **WHEN** a session is given a router that does not declare `HookRoute`
- **THEN** it raises `TypeError`

#### Scenario: AC-ROUTE-002.5 No router

- **WHEN** a say is made in a session with no router and one answering peer
- **THEN** it is addressed to nobody and the peer is not asked

### Requirement: REQ-ROUTE-003 What a router returns is checked

The session SHALL use what the router returns only when it is another peer that answers; anything else MUST be ignored with a warning, and a router that raises MUST be logged, the say going to nobody in both cases.

#### Scenario: AC-ROUTE-003.1 A bad route

- **WHEN** the router returns an id that is no answering peer
- **THEN** the say goes to nobody and a warning says the route was ignored

#### Scenario: AC-ROUTE-003.2 A failing router

- **WHEN** the router raises
- **THEN** the say is still posted, to nobody, and the failure is logged

### Requirement: REQ-ROUTE-004 SimpleRouter gives a say to the lone answering peer

`SimpleRouter` SHALL route a say that replies to nothing to the only peer that answers, when there is exactly one besides the speaker and the frontend; with several, or none, it routes to nobody. That peer's answer replies to the say and is addressed to nobody; listeners still hear the say. A listener that answers only what is addressed to nobody therefore stays quiet when the say is routed.

#### Scenario: AC-ROUTE-004.1 One peer answers

- **WHEN** the user says something in a room with one answering peer
- **THEN** that peer is asked, its answer replies to the say addressed to nobody, and listeners heard the say

#### Scenario: AC-ROUTE-004.2 Several answer

- **WHEN** the user says something in a room with two answering peers
- **THEN** nobody is asked and the say is addressed to nobody

#### Scenario: AC-ROUTE-004.3 The speaker and the frontend

- **WHEN** the only answering peer says something
- **THEN** nobody is asked, the frontend included

#### Scenario: AC-ROUTE-004.4 A listener of unaddressed says

- **WHEN** a say is routed to the lone answering peer while another peer listens for says addressed to nobody
- **THEN** the say goes to that peer and the listener hears nothing to answer

#### Scenario: AC-ROUTE-004.5 A lone peer that fails

- **WHEN** the say is routed to a peer whose `answer` raises
- **THEN** an `error` reply from that peer, naming the exception, replies to the say

### Requirement: REQ-ROUTE-005 SimpleRouter keeps a reply with its author

`SimpleRouter` SHALL route a say that replies to a message to whoever said that message, when it is another peer that answers, even in a room with several; a reply to the user, to a peer that does not answer, to a command's output or to oneself goes to nobody. A `to` the speaker gives always wins.

#### Scenario: AC-ROUTE-005.1 A reply to the user

- **WHEN** a peer's answer replies to the user's say
- **THEN** the lone answering peer was asked the user's say once and never the reply, and the reply is posted addressed to nobody

#### Scenario: AC-ROUTE-005.2 A follow-up

- **WHEN** the user replies to a peer's answer
- **THEN** the follow-up is addressed to that peer, which answers it

#### Scenario: AC-ROUTE-005.3 With several peers

- **WHEN** the user replies to one peer's answer in a room where two answer
- **THEN** only that peer is asked the follow-up

#### Scenario: AC-ROUTE-005.4 To a peer that does not answer

- **WHEN** the user replies to a peer that does not answer
- **THEN** the reply goes to nobody

#### Scenario: AC-ROUTE-005.5 To a command's output

- **WHEN** the user replies to what a command answered
- **THEN** the reply goes to nobody

#### Scenario: AC-ROUTE-005.6 An explicit recipient wins

- **WHEN** the user replies to one peer's answer but addresses the reply to another
- **THEN** the addressed peer is asked it

#### Scenario: AC-ROUTE-005.7 To oneself

- **WHEN** the user replies to their own message
- **THEN** the reply goes to nobody

### Requirement: REQ-ROUTE-006 The builders route with SimpleRouter

`build_chat_session` and `build_mcp_session` SHALL give the session a `SimpleRouter` when given no router, and the router given otherwise.

#### Scenario: AC-ROUTE-006.1 SimpleRouter unless given one

- **WHEN** each builder is called without a router, and with one
- **THEN** the first session's router is a `SimpleRouter` and the second's is the one given

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

`LLMRouter` MUST route the say to nobody, and log a warning naming the reason but never a key or the say's text, when the model's answer names no answering peer, names a peer two answering peers share, or the request fails, raises, or takes longer than its `timeout` (10 seconds by default). The say MUST still be posted, and the chat MUST NOT wait longer than `timeout` for it. A `timeout` that is not a positive number MUST be refused with `ValueError` when the router is built.

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

#### Scenario: AC-ROUTE-009.6 A timeout that is not positive

- **WHEN** a router is built with `timeout=0`
- **THEN** it raises `ValueError`

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
