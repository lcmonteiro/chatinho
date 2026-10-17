## Purpose

Decides who answers a say whose speaker named nobody: a router, rule-based by default and replaceable (by a model, for one), fills in the say's `to`, which is then the one field that says who owes it an answer.

## ADDED Requirements

### Requirement: A router decides who an unaddressed say is for
A session SHALL consult its router for every say that is said by a peer (not by `TOOL`), has `to` unset, and is not an answer. The router's result SHALL become the say's `to` before the say enters the conversation, so every listener, the archive and `context()` see the say with that `to`, and that peer's `answer` is called for it. When the router returns None, `to` MUST stay unset and no peer's `answer` is called. The session MUST NOT consult the router for a say with `to` set, for an `ask`, for anything `TOOL` writes, or for an answer.

#### Scenario: Routed to one peer
- **WHEN** a router that always returns `bot` is given, and the user says "hi"
- **THEN** the say in the conversation has `to` set to `bot`, and `bot`'s `answer` is called once for it

#### Scenario: Routed to nobody
- **WHEN** the router returns None for the user's "hi"
- **THEN** the say has `to` unset, and no peer's `answer` is called

#### Scenario: An addressed say is not routed
- **WHEN** the user says "hi" with `to` set to `sol`, and the router would return `lua`
- **THEN** the router is not consulted, and only `sol`'s `answer` is called

#### Scenario: A command's output is not routed
- **WHEN** the user runs `/help`
- **THEN** the router is consulted for neither the invocation nor its result

### Requirement: A router is declared, and is not a peer
A router SHALL be a class declaring `HookRoute`, which demands `route(msg)`, a coroutine returning a peer id or None. It is given as `ChatSession(router=…)`. A router MUST NOT be given an id, be addressed, or hear the conversation, though it may declare grants (`HookPeers`, `HookContext` and the rest) to read the room, and the session MUST grant them. Its `initialize()` and `shutdown()`, when present, MUST be called at `start()` and `close()` as a command's are. A `router=` that does not declare `HookRoute` MUST raise `TypeError`.

#### Scenario: A router reads the room
- **WHEN** a router declaring `HookRoute` and `HookPeers` is given
- **THEN** it can call `peers()` from `route`, and it does not appear in `peers()` itself

#### Scenario: Not a router
- **WHEN** `ChatSession(router=obj)` is given an object that does not declare `HookRoute`
- **THEN** it raises `TypeError`

### Requirement: What a router returns is checked
A router's result SHALL be used only when it is the id of a peer in the chat, other than the speaker, that declares `HookAnswer`. Any other result MUST be ignored with a warning, leaving `to` unset. A router that raises MUST NOT stop the say: the failure MUST be logged, and the say posted with `to` unset.

#### Scenario: The router names the speaker
- **WHEN** a router returns the speaker's own id
- **THEN** the say is posted with `to` unset, and a warning is logged

#### Scenario: The router names a peer that does not answer
- **WHEN** a router returns the id of a peer that only listens
- **THEN** the say is posted with `to` unset, and a warning is logged

#### Scenario: The router fails
- **WHEN** a router's `route` raises
- **THEN** the say is posted with `to` unset, and the failure is logged

### Requirement: The default router
Without `router=`, a session SHALL route with `SimpleRouter`, which needs nothing from the standard library outward. For a say that replies to a message (`reply_to` set), it MUST return that message's author when the author is a peer other than the speaker and the frontend and declares `HookAnswer`, and None otherwise. For any other say, it MUST return the one peer other than the speaker and the frontend that declares `HookAnswer`, and None when there is no such peer or more than one.

#### Scenario: One peer answers
- **WHEN** the user says "will it rain?" and the only peer that answers is `weather`
- **THEN** the say has `to` set to `weather`, and `weather`'s reply comes back with `reply_to` set to the say

#### Scenario: Several peers answer
- **WHEN** the user says something in a room where two peers answer
- **THEN** the say has `to` unset, and neither peer's `answer` is called

#### Scenario: The user follows up on an answer
- **WHEN** the user says "hello" in a chat whose only answering peer is `bot`, `bot` answers, and the user then says "and tomorrow?" with `reply_to` set to that answer
- **THEN** "and tomorrow?" has `to` set to `bot`, and `bot`'s `answer` is called with it

#### Scenario: Following up in a room with several peers
- **WHEN** two peers answer, the user asks `sol` with `@sol`, and then replies to `sol`'s answer
- **THEN** the reply has `to` set to `sol`, and only `sol`'s `answer` is called

#### Scenario: Replying to a peer that does not answer
- **WHEN** the user replies to a message said by a peer that only listens
- **THEN** the reply has `to` unset, and no peer's `answer` is called for it

#### Scenario: Replying to a command's output
- **WHEN** the user replies to what a command answered
- **THEN** the reply has `to` unset

#### Scenario: Replying to oneself
- **WHEN** a peer says something with `reply_to` set to a message it said itself
- **THEN** the reply has `to` unset

#### Scenario: A lone peer fails
- **WHEN** a say is routed to the lone answering peer and its `answer` raises
- **THEN** an `error` reply to the say is posted in that peer's name

### Requirement: An answer is addressed to nobody
An answer SHALL be posted with `to` unset. An answer is what a peer's `answer` returned, a reply the session posts in a peer's name (the `error` reply when its `answer` raises, and the reply saying there are too many nested asks), and a say whose `reply_to` names a message addressed to the speaker. An answer MUST NOT be routed, and MUST NOT be handed to any peer's `answer`.

#### Scenario: An answer has no recipient
- **WHEN** a peer asks `sol` with `ask(sol, "rain?")`, and `sol` answers
- **THEN** the question has `to` set to `sol`, and the answer has `to` unset and `reply_to` set to the question

#### Scenario: A late answer is not routed
- **WHEN** `bot` is asked a question, returns None from `answer`, and later says a reply to the question, in a room where the asker also answers
- **THEN** the reply has `to` unset, the router is not consulted, and the asker's `answer` is not called

#### Scenario: The user answers a question put to them
- **WHEN** a peer asks the user, and the user says a reply to that question
- **THEN** the reply has `to` unset and resolves the ask

### Requirement: A slow router does not hold the terminal
A say SHALL enter the conversation only once its router has returned. The terminal MUST NOT wait for that: what the user sends MUST leave the input free while the router decides, as a `/command` already does.

#### Scenario: A router that takes a second
- **WHEN** a router sleeps one second before returning, and the user sends "hi"
- **THEN** the input is cleared and accepts new text before the router returns, and "hi" appears in the log once it has
