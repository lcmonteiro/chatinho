# Spec Delta

## Purpose

Lets an asker lend a credential (for example an LLM API key or a short-lived token) to the remote session that answers its question, following A2A's principle: the server declares what it needs, the credential travels out of band, never in message content, and lives only while that one question is being answered. It is opt-in, and it is how a remote peer borrows the asker's intelligence.

## ADDED Requirements

### Requirement: Credential hook
chatinho SHALL provide `HookCredential`, a grant-only hook that gives a peer `credential(msg_id, name) -> str`: the credential called `name` delegated for message `msg_id`. The session MUST route the request to the frontend if the frontend declares `HookServeCredential`, a hook demanding `serve_credential(msg_id, name) -> str`; with no frontend serving credentials, or no credential `name` delegated for that message, `credential` MUST raise `CredentialUnavailable`. Both hooks MUST be documented in `docs/SPEC.md`.

#### Scenario: Delegated credential for the question
- **WHEN** a peer declaring `HookCredential` calls `credential(msg_id, "llm")` for a question that came with a delegated `llm` credential
- **THEN** it gets that credential's value

#### Scenario: Nothing delegated
- **WHEN** a peer calls `credential(msg_id, "llm")` for a question that came without one, or in a session whose frontend does not serve credentials
- **THEN** it raises `CredentialUnavailable`

### Requirement: The server declares what it needs
`McpFrontend` SHALL accept the names of the credentials its peers may use, each with a short description, and announce them to clients in its `server/discover` result, as the capability extension `chatinho/credentials`. It MUST NOT accept a delegated credential whose name it did not declare. With nothing declared, the server MUST ignore every delegated credential.

#### Scenario: Declared at discovery
- **WHEN** a server is created declaring `llm` ("OpenAI-compatible API key") and a client discovers it
- **THEN** the client sees `llm` and its description among the server's declared credentials

#### Scenario: Undeclared credential ignored
- **WHEN** a client delegates a credential `cloud` the server did not declare
- **THEN** no peer can obtain it

### Requirement: Credentials travel out of band
`McpConnector` SHALL delegate only when configured to, with a mapping from credential name to either a value or a function returning a value for each question (so it can mint short-lived tokens). It MUST send only the configured credentials the server declared, in the request's MCP metadata, never in the question text. Over HTTP it MUST refuse to delegate to a URL that is not `https`, unless the host is a loopback address. Without the configuration, the connector MUST NOT send any credential.

#### Scenario: Sent with the question
- **WHEN** a connector configured with `delegate={"llm": key}` asks a server that declared `llm`
- **THEN** the credential is in that request's metadata and not in the question's text

#### Scenario: Not declared, not sent
- **WHEN** the same connector asks a server that declared no credentials
- **THEN** no credential is sent

#### Scenario: Plain HTTP refused
- **WHEN** a connector configured to delegate connects to `http://lab.example:8000`
- **THEN** it does not send the credential and its reply says delegation requires HTTPS

#### Scenario: Token per question
- **WHEN** the configured value for `llm` is a function
- **THEN** it is called once for each question asked, and its result is what is delegated

### Requirement: Alive only while the question is answered
A delegated credential SHALL be bound to the question it came with, and kept only in memory; it MUST reach only the session the connector connects to. The server MUST discard it when that question's result is returned, whatever the status. It MUST NOT be written to the conversation, the store, attachments or logs, and its representation in errors and tracebacks MUST be redacted. A connector MUST NOT delegate a credential it obtained through `credential`; it delegates only its own configured ones.

#### Scenario: Gone after the answer
- **WHEN** a peer has answered a question that came with `llm`, and then calls `credential` for that question's id
- **THEN** it raises `CredentialUnavailable`

#### Scenario: Gone on timeout
- **WHEN** a question with a delegated credential ends in `timeout`
- **THEN** the credential is discarded at that moment, even if the peer is still working

#### Scenario: Never in history
- **WHEN** the conversation context and the store are read after a question with a delegated credential
- **THEN** the credential's value appears nowhere
