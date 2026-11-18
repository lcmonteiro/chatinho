# Spec Delta: framework

## MODIFIED Requirements

### Requirement: REQ-CORE-002 A name is not an address

Every peer and command SHALL have a visible name, set by `@connector`, `@tool`, `@frontend` or `@backend`, which an instance MAY override; an undecorated class falls back to its class name, and a name that is not a non-empty string MUST be refused with `ValueError`. Messages MUST be routed by id, never by name, so renaming a peer does not change where its messages go. A `@tool` also carries a description. A `@connector` MAY carry a one-line description of what the peer is for, which an instance MAY override; it defaults to empty, and a description that is not a string MUST be refused with `ValueError`.

#### Scenario: AC-CORE-002.1 Renaming keeps the address

- **GIVEN** a peer registered at id 1
- **WHEN** its name is changed and id 1 is asked
- **THEN** the same peer answers, and the session finds id 1 under the new name

#### Scenario: AC-CORE-002.2 A class names itself, an instance overrides

- **GIVEN** a class decorated `@connector("weather")`
- **WHEN** one instance sets its own `name`
- **THEN** that instance has the new name and the others keep `weather`

#### Scenario: AC-CORE-002.3 A tool carries its description

- **WHEN** a class is decorated `@tool("deploy", "Ship it")`
- **THEN** its name is `deploy` and its description `Ship it`

#### Scenario: AC-CORE-002.4 An undecorated class

- **WHEN** the name of an instance of an undecorated class is read
- **THEN** it is the class's own name

#### Scenario: AC-CORE-002.5 An empty name

- **WHEN** `connector`, `tool`, `backend` or `frontend` is given an empty, blank or non-string name
- **THEN** it raises `ValueError`

#### Scenario: AC-CORE-002.6 A peer carries its description

- **GIVEN** a class decorated `@connector("weather", description="Forecasts by city")`
- **WHEN** one instance sets its own `description`
- **THEN** that instance has the new description and the others keep `Forecasts by city`

#### Scenario: AC-CORE-002.7 No description

- **WHEN** a class is decorated `@connector("weather")`
- **THEN** its description is empty

#### Scenario: AC-CORE-002.8 A description that is not a string

- **WHEN** `connector` is given a description that is not a string
- **THEN** it raises `ValueError`
