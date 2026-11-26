# Spec Delta: connectors

## ADDED Requirements

### Requirement: REQ-CONN-026 An agent answers with a key lent on the question

An agent connector whose model is an `Endpoint` SHALL call its model, for one
run, with the credential lent on the question under its `credential` name
(default `llm`) when there is one, and otherwise with its endpoint's key, read
as REQ-CONN-018 says. With a key lent, its endpoint MUST NOT need a key of its
own. Two runs at once MUST each use their own question's key, and a peer the
agent asks during a run MUST NOT be given the lent key unless its own question
lends one. An agent whose model is not an `Endpoint` SHALL ignore a lent key and
log a warning saying so, once. A lent key MUST NOT appear in a reply, in the
connector's `repr` or in any log record.

#### Scenario: AC-CONN-026.1 Answered with the asker's key

- **GIVEN** an agent whose `Endpoint` has its own key `sk-own`
- **WHEN** it answers a question lent `llm` = `sk-lent`, then one lent nothing
- **THEN** the first run reaches the model with `sk-lent` and the second with `sk-own`

#### Scenario: AC-CONN-026.2 No key of its own

- **GIVEN** an agent whose `Endpoint` has no key
- **WHEN** it answers a question lent `llm` = `sk-lent`
- **THEN** it answers from the model, which was called with `sk-lent`

#### Scenario: AC-CONN-026.3 Another credential name

- **GIVEN** an agent built with `credential="openai"`
- **WHEN** it answers a question lent `openai` = `sk-a` and `llm` = `sk-b`
- **THEN** the model is called with `sk-a`

#### Scenario: AC-CONN-026.4 Two questions at once

- **WHEN** an agent answers two questions concurrently, lent `sk-one` and `sk-two`
- **THEN** each run's requests carry its own question's key

#### Scenario: AC-CONN-026.5 Not passed to the peer it asks

- **GIVEN** two agents with `Endpoint` models, the second with its own key `sk-own`
- **WHEN** the first, asked with `llm` = `sk-lent`, asks the second during its run
- **THEN** the second's model is called with `sk-own`

#### Scenario: AC-CONN-026.6 A model that is not an Endpoint

- **GIVEN** an agent whose model is a ready chat model
- **WHEN** it answers two questions lent a key
- **THEN** both are answered by that model, and one warning says the lent key was ignored

#### Scenario: AC-CONN-026.7 The key is never shown

- **WHEN** an agent answers a question lent `sk-lent` and its model call fails
- **THEN** `sk-lent` is in neither the reply, the connector's `repr`, nor any log record
