# Spec Delta: agents

## ADDED Requirements

### Requirement: REQ-AGENT-013 An agent logs its runs and its builds

`AgentPeer` SHALL log, on the `chatinho` loggers at DEBUG or INFO, each run with the peer's name, the message's id, how long it took and its outcome (answered, interrupted, or the error's type), and each time it builds its agent, with the factory's name and the number of tools it was given. No record MUST hold the question, the answer's text or a key; failures keep their warnings.

#### Scenario: AC-AGENT-013.1 A run

- **GIVEN** an agent peer named `dev` with a scripted model
- **WHEN** it is asked a question
- **THEN** a record names `dev`, the question's id, a duration and that it answered

#### Scenario: AC-AGENT-013.2 A run that fails

- **GIVEN** a scripted model that raises
- **WHEN** the peer is asked
- **THEN** a record names the question's id and the error's type

#### Scenario: AC-AGENT-013.3 A build

- **WHEN** the peer is asked its first question
- **THEN** a record names the factory and the number of tools the agent was built with

#### Scenario: AC-AGENT-013.4 Nothing said

- **GIVEN** an agent peer capturing every `chatinho` record from DEBUG up
- **WHEN** it is asked a distinctive question and answers a distinctive text
- **THEN** no captured record holds either text
