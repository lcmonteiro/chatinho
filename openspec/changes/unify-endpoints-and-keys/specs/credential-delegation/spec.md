## MODIFIED Requirements

### Requirement: Credentials travel out of band
`McpConnector` SHALL delegate only when configured to, with a mapping from credential name to one of:
- a value;
- a function returning a value for each question, so it can mint short-lived tokens;
- a key source.

It MUST send only the configured credentials the server declared, in the request's MCP metadata, never in the question text. A key source MUST be read for each question, under that source's own caching rules. A source that cannot yield its key MUST make the connector answer that question with an `error` reply carrying the source's error, which names the reference and never a value; the question MUST NOT be sent.

Choosing a transport fit to carry a credential (HTTPS) is the responsibility of whoever builds the system; the connector does not check it. Without the configuration, the connector MUST NOT send any credential.

#### Scenario: Sent with the question
- **WHEN** a connector configured with `delegate={"llm": key}` asks a server that declared `llm`
- **THEN** the credential is in that request's metadata and not in the question's text

#### Scenario: Not declared, not sent
- **WHEN** the same connector asks a server that declared no credentials
- **THEN** no credential is sent

#### Scenario: Token per question
- **WHEN** the configured value for `llm` is a function
- **THEN** it is called once for each question asked, and its result is what is delegated

#### Scenario: Lent from a key source
- **WHEN** the configured value for `llm` is `Env("OPENAI_API_KEY")` and that variable is `sk-env`
- **THEN** `sk-env` is what is delegated

#### Scenario: A source that cannot read
- **WHEN** the configured value for `llm` is `Env("UNSET")` and the variable is unset
- **THEN** the connector answers with an `error` reply naming `UNSET`, and the question is not sent to the server
