# Spec Delta: routers

## ADDED Requirements

### Requirement: REQ-ROUTE-012 LLMRouter sends extra request headers

`LLMRouter` SHALL accept optional `headers`, a mapping of header names to
values, and SHALL send every one of them with every request it makes to the
model, whether it asks with its endpoint's own key or with a key lent on the
say as `llm`. It SHALL keep a copy taken when it is built, so a later change
to the caller's mapping has no effect. A router built with no `headers`, or an
empty mapping, SHALL send no header of its own beyond what it sends today.
`headers` that are not a mapping, hold a name or a value that is not a string,
or name `Authorization` in any letter case MUST be refused with `ValueError`
when the router is built, the error naming the offending header but never a
value. No header value SHALL appear in the router's `repr` or in any warning
it logs.

#### Scenario: AC-ROUTE-012.1 Its own key

- **GIVEN** a router built with `headers={"Editor-Version": "vscode/1.95.0"}` and its own key
- **WHEN** a say with two answering peers is routed
- **THEN** the request is made with that key and carries `Editor-Version: vscode/1.95.0`

#### Scenario: AC-ROUTE-012.2 A lent key

- **GIVEN** a router built with `headers={"Editor-Version": "vscode/1.95.0"}`, and a say lent the key `client-key` as `llm`
- **WHEN** the model is asked
- **THEN** the request is made with `client-key` and carries `Editor-Version: vscode/1.95.0`

#### Scenario: AC-ROUTE-012.3 No headers

- **GIVEN** a router built without `headers`, and one built with `headers={}`
- **WHEN** each routes a say to the model
- **THEN** neither client is given any header of the router's

#### Scenario: AC-ROUTE-012.4 A copy

- **GIVEN** a router built from a dict `{"X-A": "1"}`
- **WHEN** the dict is changed to `{"X-A": "2"}` afterwards and a say is routed
- **THEN** the request carries `X-A: 1`

#### Scenario: AC-ROUTE-012.5 Malformed headers

- **WHEN** a router is built with `headers=["X-A"]`, `{"X-A": 1}` or `{1: "x"}`
- **THEN** it raises `ValueError`

#### Scenario: AC-ROUTE-012.6 Authorization refused

- **WHEN** a router is built with `headers={"authorization": "Bearer sk-secret"}`
- **THEN** it raises `ValueError` naming `authorization`, and `sk-secret` is not in the error

#### Scenario: AC-ROUTE-012.7 Values never shown

- **GIVEN** a router built with `headers={"X-Token": "tok-secret"}` whose request fails
- **WHEN** a say is routed and its `repr` is taken
- **THEN** `tok-secret` appears in neither the `repr` nor any logged warning
