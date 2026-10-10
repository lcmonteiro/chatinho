# package-layout Specification

## Purpose

Fixes where chatinho's public names live: the core under unprefixed modules, each frontend under `chatinho.frontends`, and one builder per kind of session in `chatinho.builder`.

## Requirements

### Requirement: The core lives in unprefixed modules
The session, the message types and the hooks SHALL be importable from `chatinho.session`, `chatinho.message` and `chatinho.hooks`, and the package root MUST keep exporting the same names it exports today (other than those this change renames or moves). The modules `chatinho.chat_session`, `chatinho.chat_message`, `chatinho.chat_hooks`, `chatinho.chat_app`, `chatinho.chat_log`, `chatinho.chat_input`, `chatinho.chat_style`, `chatinho.chat_clipboard` and `chatinho.chat_builder` MUST NOT exist, and no compatibility alias for them is provided. Importing `chatinho` or any of the core modules MUST NOT import a terminal UI library.

#### Scenario: Importing the core by its new name
- **WHEN** code runs `from chatinho.session import ChatSession`
- **THEN** it gets the same `ChatSession` that `from chatinho import ChatSession` gives

#### Scenario: Old module names are gone
- **WHEN** code runs `import chatinho.chat_session`
- **THEN** it fails with `ModuleNotFoundError`

#### Scenario: The core stays headless
- **WHEN** `chatinho` and its core modules are imported in an environment without the `tui` extra
- **THEN** the import succeeds

### Requirement: Each frontend lives under chatinho.frontends
The terminal SHALL be the class `ChatFrontend`, importable from `chatinho.frontends.chat`, from `chatinho.frontends` and from `chatinho`; the MCP frontend SHALL stay `McpFrontend` in `chatinho.frontends.mcp`, also importable from `chatinho.frontends` and `chatinho`. Everything the terminal is made of, its colour scheme `ChatStyle` included, MUST live inside `chatinho.frontends.chat`, and it is the only part of the package that imports the terminal UI library. The name `ChatApp` MUST NOT exist. Reading `ChatFrontend` or `ChatStyle` off `chatinho` without the `tui` extra installed MUST raise `ImportError` naming `chatinho[tui]`.

#### Scenario: The terminal by its new name
- **WHEN** code runs `from chatinho import ChatFrontend` with the `tui` extra installed
- **THEN** it gets the terminal frontend, the same class as `chatinho.frontends.chat.ChatFrontend`

#### Scenario: The terminal without its extra
- **WHEN** code reads `chatinho.ChatFrontend` without the `tui` extra installed
- **THEN** it raises `ImportError` whose message says to install `chatinho[tui]`

### Requirement: One builder per kind of session
chatinho SHALL provide `build_chat_session` and `build_mcp_session` in `chatinho.builder`, both also exported from `chatinho`. `build_chat_session` MUST take the parameters `build_chat` took and return a `ChatSession` whose frontend is a `ChatFrontend` built from them. `build_mcp_session` MUST take the session's `connectors`, `commands` and `backend` and the `McpFrontend`'s `name`, `token`, `host`, `port` and `credentials`, and return a `ChatSession` whose frontend is an `McpFrontend` built from them; it MUST refuse a missing token as `McpFrontend` does. `build_chat` MUST NOT exist.

#### Scenario: A chat with a terminal
- **WHEN** code calls `build_chat_session(commands=[HelpCommand()], title="Demo")`
- **THEN** it gets a `ChatSession` whose peer zero is a `ChatFrontend` titled `Demo`, with `/help` available

#### Scenario: A chat served over MCP
- **WHEN** code calls `build_mcp_session(connectors=[agent], token="t", port=9000)`
- **THEN** it gets a `ChatSession` whose peer zero is an `McpFrontend` named `master` serving on port 9000, with `agent` as a peer

#### Scenario: An MCP chat without a token
- **WHEN** code calls `build_mcp_session(token="")`
- **THEN** it raises `ValueError`

### Requirement: The builders need both frontend extras
`chatinho.builder` imports both frontends, so `build_chat_session` and `build_mcp_session` MUST each need the `tui` and the `mcp` extras. Reading either builder off `chatinho` without both installed MUST raise `ImportError` naming `chatinho[tui,mcp]`. Each frontend MUST still need only its own extra: `ChatFrontend` works without the `mcp` extra, and `McpFrontend` without the `tui` extra, so a caller with one extra builds the `ChatSession` with that frontend by hand.

#### Scenario: A builder without the MCP library
- **WHEN** the `mcp` extra is not installed and code reads `chatinho.build_chat_session`
- **THEN** it raises `ImportError` whose message says to install `chatinho[tui,mcp]`

#### Scenario: A builder without the terminal library
- **WHEN** the `tui` extra is not installed and code reads `chatinho.build_mcp_session`
- **THEN** it raises `ImportError` whose message says to install `chatinho[tui,mcp]`

#### Scenario: A frontend without the other extra
- **WHEN** only the `tui` extra is installed and code reads `chatinho.ChatFrontend`
- **THEN** it gets the terminal frontend
