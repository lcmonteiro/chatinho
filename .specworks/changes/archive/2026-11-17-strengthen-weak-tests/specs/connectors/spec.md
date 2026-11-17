# Spec Delta: connectors

## MODIFIED Requirements

### Requirement: REQ-CONN-020 DeepAgentConnector is built from create_deep_agent's parameters

`DeepAgentConnector` SHALL take its name, a `model`, `tools`, the chat options and any keyword argument `create_deep_agent` accepts, passing them on unchanged, except that deep agents' own `memory` is given as `agent_memory`. A `backend` option MUST raise `TypeError` saying the workspace is the backend, and an unknown option `TypeError` naming it. It uses its workspace by default.

#### Scenario: AC-CONN-020.1 Deep agents' options reach the agent

- **WHEN** a connector is created with deep agents' `subagents` option holding a `researcher` with the system prompt `Research.`, and its model calls the `task` tool for `researcher`
- **THEN** the subagent runs with the system prompt `Research.`, its answer reaches the model, and the connector answers

#### Scenario: AC-CONN-020.2 memory and agent_memory

- **WHEN** a connector is created with `memory=Query().last(5)` and `agent_memory=["/AGENTS.md"]`
- **THEN** the question comes last, the oldest messages of a longer conversation are not sent, and the model's system prompt holds what `/AGENTS.md` says in the connector's workspace

#### Scenario: AC-CONN-020.3 A backend is refused

- **WHEN** a connector is created with `backend=...`
- **THEN** creating it raises `TypeError` saying the workspace is its backend

#### Scenario: AC-CONN-020.4 An unknown option

- **WHEN** a connector is created with an option `create_deep_agent` does not take
- **THEN** creating it raises `TypeError` naming it

#### Scenario: AC-CONN-020.5 Its workspace by default

- **WHEN** a connector is created with no `workspace` option
- **THEN** it uses its workspace

