## REMOVED Requirements

### Requirement: The builders need both frontend extras
**Reason**: Coupling each builder to both extras is a side effect of `chatinho.builder` importing both frontends at module level, not a property anyone needs. It made the terminal builder require the heaviest extra (`mcp`, which brings pydantic, starlette and uvicorn).
**Migration**: None needed for callers with both extras installed. A caller with only `chatinho[tui]` can now use `build_chat_session`, and a caller with only `chatinho[mcp]` can use `build_mcp_session`.

## ADDED Requirements

### Requirement: Each builder needs only its own frontend's extra
`build_chat_session` SHALL need only the `tui` extra and `build_mcp_session` only the `mcp` extra. Reading `build_chat_session` off `chatinho` without the `tui` extra MUST raise `ImportError` naming `chatinho[tui]`, and reading `build_mcp_session` without the `mcp` extra MUST raise `ImportError` naming `chatinho[mcp]`. Importing `chatinho.builder` MUST NOT itself require either extra. Each frontend MUST still need only its own extra.

#### Scenario: The terminal builder without the MCP library
- **WHEN** only the `tui` extra is installed and code calls `chatinho.build_chat_session()`
- **THEN** it returns a session whose frontend is the terminal

#### Scenario: The MCP builder without the terminal library
- **WHEN** only the `mcp` extra is installed and code calls `chatinho.build_mcp_session(token="t")`
- **THEN** it returns a session whose frontend is the MCP server

#### Scenario: A builder without its own library
- **WHEN** the `tui` extra is not installed and code reads `chatinho.build_chat_session`
- **THEN** it raises `ImportError` whose message says to install `chatinho[tui]`

#### Scenario: A frontend without the other extra
- **WHEN** only the `tui` extra is installed and code reads `chatinho.ChatFrontend`
- **THEN** it gets the terminal frontend
