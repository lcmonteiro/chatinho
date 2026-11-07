# Spec Delta

## ADDED Requirements

### Requirement: Workspaces as tools
`AgentConnector` SHALL declare `HookWorkspace` and SHALL take a `workspace` option, `False` by default. When it is created with `workspace=True` and its session has a workspace provider, the agent SHALL have, besides its other tools, one tool per operation of its own workspace, named `ws_` followed by the operation's name, described by the operation's description, and taking the operation's parameters. It SHALL also have one tool per read operation, named `ws_` followed by the operation's name and `_of`, that takes the name of the peer whose workspace it reads in a `workspace` parameter. The tools MUST be derived from the operations the provider's classes declare, so an operation a project adds becomes a tool with no change to the connector. A tool whose operation raises MUST return the failure as text naming the kind of error, never end the run. A `diff` result MUST become an attachment of the answer, as any tool's file does. A connector created without `workspace=True` MUST have no `ws_` tools and MUST NOT cause a workspace to be created. One whose session has no provider MUST have no `ws_` tools, MUST still answer, and SHALL log once that it has none.

#### Scenario: Its own workspace as tools
- **WHEN** the connector is created with `workspace=True` and is asked a question
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

#### Scenario: Not asked for
- **WHEN** the connector is created without `workspace=True` in a session with a workspace provider
- **THEN** the agent has no `ws_` tools, and no workspace is created for it

#### Scenario: No provider
- **WHEN** the connector is created with `workspace=True` in a session given no `workspaces`
- **THEN** it answers, with no `ws_` tools, and logs that the session has no workspace provider
