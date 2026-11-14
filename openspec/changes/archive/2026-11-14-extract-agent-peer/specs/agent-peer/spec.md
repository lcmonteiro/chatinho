# Spec Delta

## Purpose

A chat peer around any LangChain agent. One base class holds what every agent connector does in a chat, and receives a factory that makes the agent. The factory states which options it accepts, which workspace operations its own tools already reach, and builds the agent with the chat running.

## ADDED Requirements

### Requirement: A peer around any agent factory
`AgentPeer` SHALL take its name in the chat, a `model`, a `factory`, `tools`, the chat options (`memory`, `peers`, `commands`, `ask_user`, `link_retries`, `workspace`) and any other keyword argument the factory accepts. It SHALL behave in the chat as `BasicAgentConnector` does, whatever the factory builds: one run per question and per user say it responds to, failures as `ERROR` replies naming the peer, the chat as tools, memory from `context()`, attachments and the link check. A factory is any object with a `name`, an `options` set, a `covered` set and an `async build(model, tools, options, peer)` method. `AgentPeer` MUST call `build` when its graph is first needed and whenever the shape of the chat changes, never when it is created. `build` MUST receive the model, the given tools plus the chat's tools, and the options the peer was given (with `name` defaulting to the peer's name). It MUST also receive the peer, so the factory can use the peer's grants.

#### Scenario: A custom factory
- **WHEN** an `AgentPeer` is created with a factory whose `build` returns a LangChain agent, and the peer is asked a question
- **THEN** the factory's `build` is awaited once, with the chat's `ask_` tools among the tools it is given, and the peer answers with that agent's last message

#### Scenario: Not built when created
- **WHEN** an `AgentPeer` is created and never asked anything
- **THEN** the factory's `build` is never called

#### Scenario: Rebuilt for a new peer
- **WHEN** a peer joins the chat after the `AgentPeer` has answered once, and the `AgentPeer` is asked again
- **THEN** `build` is called a second time, with the new peer's `ask_` tool

### Requirement: The factory says what it accepts
A keyword argument that is not a chat option and is not in the factory's `options` MUST raise `TypeError` when the peer is created, naming the argument and the factory's `name`.

#### Scenario: An option the factory does not take
- **WHEN** an `AgentPeer` is created with a factory named `my_factory` whose `options` lack `temperature`, and with `temperature=0.2`
- **THEN** creating it raises `TypeError` naming `my_factory` and `temperature`

### Requirement: The factory says what its own tools cover
With `workspace=True` and a workspace provider, the peer SHALL have `ws_` tools, as `BasicAgentConnector` does, for every workspace operation except those named in the factory's `covered` set. It MUST have no `ws_<op>` or `ws_<op>_of` tool for an operation in `covered`.

#### Scenario: Covered operations get no tools
- **WHEN** an `AgentPeer` has `workspace=True`, a workspace provider, and a factory whose `covered` is `{"read"}`
- **THEN** the agent has no `ws_read` and no `ws_read_of`, and has `ws_write` and `ws_diff_of`

### Requirement: Where the base and the factories are imported from
`AgentPeer`, `AgentFactory` and `BasicAgent` SHALL be importable from `chatinho.helpers.agent` with the `langchain` extra. `DeepAgent` SHALL be importable from there with the `deepagents` extra. Importing `AgentPeer` or `BasicAgent` MUST NOT import `deepagents`. None of them SHALL be exported from `chatinho`.

#### Scenario: The basic pieces do not need deep agents
- **WHEN** code imports `AgentPeer` and `BasicAgent` from `chatinho.helpers.agent`
- **THEN** no `deepagents` module is imported

#### Scenario: Not in the top-level API
- **WHEN** code reads `chatinho.AgentPeer`
- **THEN** it raises `AttributeError`
