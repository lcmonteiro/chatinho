# Spec Delta: connectors

## ADDED Requirements

### Requirement: REQ-CONN-027 The model an Endpoint becomes takes a key per call

The chat model an `Endpoint` becomes SHALL be callable as any LangChain chat
model is, asynchronously, and SHALL take an optional `api_key`, a `Secret`, on
each call. A call given one MUST reach the model with that key; a call given
none MUST use the key the run's configuration carries as `api_key` under
`configurable`, and with neither, its endpoint's own key, read as REQ-CONN-018
says. The parameter wins over the configuration. Tools bound to the model MUST
keep this behaviour. The model MUST NOT keep a key it was given after the call
returns, and a key MUST NOT appear in its `repr`. It is asynchronous only: a
synchronous call MUST raise `NotImplementedError` without reaching the model.

#### Scenario: AC-CONN-027.1 A key on the call

- **GIVEN** the model of an `Endpoint` whose own key is `sk-own`
- **WHEN** it is called with `api_key=Secret("sk-call")`, then with no key
- **THEN** the first request carries `sk-call` and the second `sk-own`

#### Scenario: AC-CONN-027.2 A key in the run's configuration

- **GIVEN** the model of an `Endpoint` whose own key is `sk-own`
- **WHEN** it is called with `configurable={"api_key": Secret("sk-config")}`, then with that and `api_key=Secret("sk-call")`
- **THEN** the first request carries `sk-config` and the second `sk-call`

#### Scenario: AC-CONN-027.3 Bound tools keep it

- **WHEN** tools are bound to the model and the result is called with `api_key=Secret("sk-call")`
- **THEN** the request carries `sk-call` and the tools

#### Scenario: AC-CONN-027.4 Nothing kept

- **WHEN** the model has been called with `api_key=Secret("sk-call")`
- **THEN** `sk-call` is in neither its `repr` nor any of its attributes

#### Scenario: AC-CONN-027.5 Asynchronous only

- **WHEN** the model is called synchronously
- **THEN** it raises `NotImplementedError` and no request is made
