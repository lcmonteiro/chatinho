# Spec Delta: connectors

## ADDED Requirements

### Requirement: REQ-CONN-025 A connector logs each request it makes

`OpenAIConnector` and `McpConnector` SHALL log, on the `chatinho` loggers at DEBUG or INFO, each request they make for a message: the connector's name, the message's id, the model or server asked, how long it took, and its outcome (answered, or the error's type). No record MUST hold the prompt, the answer's text or a key, whether configured or lent; failures keep their warnings.

#### Scenario: AC-CONN-025.1 A model answers

- **GIVEN** an `OpenAIConnector` named `gpt` with a stubbed model
- **WHEN** it is asked a question
- **THEN** a record names `gpt`, the question's id, the model, a duration and that it answered

#### Scenario: AC-CONN-025.2 A model fails

- **GIVEN** a stubbed model whose request raises an API error
- **WHEN** the connector is asked
- **THEN** a record names the question's id and the error's type

#### Scenario: AC-CONN-025.3 A remote session answers

- **GIVEN** an `McpConnector` connected to a served remote session
- **WHEN** it is asked a question
- **THEN** a record names the connector, the question's id, the server, a duration and the answer's status

#### Scenario: AC-CONN-025.4 Nothing said, no key

- **GIVEN** an `OpenAIConnector` capturing every `chatinho` record from DEBUG up, with a configured key and a lent one
- **WHEN** it is asked a distinctive question and answers a distinctive text
- **THEN** no captured record holds either text or either key
