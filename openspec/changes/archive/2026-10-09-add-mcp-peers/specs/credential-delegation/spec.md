# Spec Delta

## Purpose

Lets an asker lend a credential (for example an LLM API key or a short-lived token) to the remote session that answers its question, following A2A's principle: the server declares what it needs, the credential travels out of band, never in message content, and lives only while that one question is being answered. It is opt-in, and it is how a remote peer borrows the asker's intelligence.

## ADDED Requirements

### Requirement: Credentials ride on the message
`ChatMessage` SHALL carry `credentials`, keys by name wrapped in `Secret`, empty by default. The `say` grant MUST accept `credentials=` and put that very mapping on the message it says, so whoever lent it can clear it. A peer answering a message MUST find the credentials lent for it on that message, and MAY use them for that message alone; each message may bring different keys, so one peer may work with a different key per message. Credentials MUST NOT appear in the message's text or `repr`, and the archive MUST NOT keep them.

#### Scenario: A key per message
- **WHEN** a peer answers three messages, the first lent `llm` = `sk-one`, the second `sk-two`, the third nothing
- **THEN** it finds `sk-one`, `sk-two` and no `llm` on them, in that order

#### Scenario: Never shown
- **WHEN** a message carrying a credential is printed or read back from the archive
- **THEN** the credential's value appears nowhere

### Requirement: The server declares what it needs
`McpFrontend` SHALL accept the names of the credentials its peers may use, each with a short description, and announce them to clients in its `server/discover` result, as the capability extension `chatinho/credentials`. It MUST NOT accept a delegated credential whose name it did not declare. With nothing declared, the server MUST ignore every delegated credential.

#### Scenario: Declared at discovery
- **WHEN** a server is created declaring `llm` ("OpenAI-compatible API key") and a client discovers it
- **THEN** the client sees `llm` and its description among the server's declared credentials

#### Scenario: Undeclared credential ignored
- **WHEN** a client delegates a credential `cloud` the server did not declare
- **THEN** no peer can obtain it

### Requirement: Credentials travel out of band
`McpConnector` SHALL delegate only when configured to, with a mapping from credential name to either a value or a function returning a value for each question (so it can mint short-lived tokens). It MUST send only the configured credentials the server declared, in the request's MCP metadata, never in the question text. Choosing a transport fit to carry a credential (HTTPS) is the responsibility of whoever builds the system; the connector does not check it. Without the configuration, the connector MUST NOT send any credential.

#### Scenario: Sent with the question
- **WHEN** a connector configured with `delegate={"llm": key}` asks a server that declared `llm`
- **THEN** the credential is in that request's metadata and not in the question's text

#### Scenario: Not declared, not sent
- **WHEN** the same connector asks a server that declared no credentials
- **THEN** no credential is sent

#### Scenario: Token per question
- **WHEN** the configured value for `llm` is a function
- **THEN** it is called once for each question asked, and its result is what is delegated

### Requirement: Alive only while the message is answered
A delegated credential SHALL ride only on the message it came with, and be kept only in memory; it MUST reach only the session the connector connects to. The frontend MUST clear it from that message when the message's result is returned, whatever the status. It MUST NOT be written to the text, the store, attachments or logs, and its representation in errors and tracebacks MUST be redacted. A connector MUST NOT delegate a credential it found on a message; it delegates only its own configured ones.

#### Scenario: Gone after the answer
- **WHEN** a message that came with `llm` has been answered
- **THEN** the message carries no credential any more

#### Scenario: Gone when the client gives up
- **WHEN** a client ends a call that came with a delegated credential before any reply comes
- **THEN** the credential is discarded at that moment, even if the peer is still working

#### Scenario: Never in history
- **WHEN** the conversation context and the store are read after a question with a delegated credential
- **THEN** the credential's value appears nowhere
