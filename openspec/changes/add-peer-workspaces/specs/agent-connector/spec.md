# Spec Delta

## ADDED Requirements

### Requirement: Workspaces as tools
When the connector declares `HookWorkspace` and its session has a workspace provider, the agent SHALL have, besides its other tools, one tool per operation of its own workspace, named `ws_` followed by the operation's name, described by the operation's description, and taking the operation's parameters. It SHALL also have one tool per read operation, named `ws_` followed by the operation's name and `_of`, that takes the name of the peer whose workspace it reads in a `workspace` parameter. The tools MUST be derived from the operations the provider's classes declare, so an operation a project adds becomes a tool with no change to the connector. A tool whose operation raises MUST return the failure as text naming the kind of error, never end the run. A `diff` result MUST become an attachment of the answer, as any tool's file does. A connector that does not declare `HookWorkspace`, or whose session has no provider, MUST have no `ws_` tools.

#### Scenario: Its own workspace as tools
- **WHEN** the connector declares `HookWorkspace` and is asked a question
- **THEN** the agent has `ws_ls`, `ws_read`, `ws_glob`, `ws_grep`, `ws_diff`, `ws_log`, `ws_write`, `ws_edit`, `ws_delete` and `ws_commit`

#### Scenario: Reading another peer's workspace
- **WHEN** the agent calls `ws_read_of` with `workspace="dev"` and `path="a.txt"`
- **THEN** the tool returns `a.txt` as it is in dev's workspace, and there is no tool that writes to dev's workspace

#### Scenario: An added operation
- **WHEN** the provider's view class adds an operation `symbols`
- **THEN** the agent has `ws_symbols` and `ws_symbols_of`

#### Scenario: An operation fails
- **WHEN** the agent calls `ws_read` with `../secret`
- **THEN** the tool returns text naming `ValueError`, and the agent still answers

#### Scenario: Not declared
- **WHEN** the connector does not declare `HookWorkspace`
- **THEN** the agent has no `ws_` tools
