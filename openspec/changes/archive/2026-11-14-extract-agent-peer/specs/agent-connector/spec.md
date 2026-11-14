# Spec Delta

## MODIFIED Requirements

### Requirement: Built from create_agent's parameters
`BasicAgentConnector` SHALL take its name in the chat, a `model` and `tools`, plus any other keyword argument `create_agent` accepts (`system_prompt`, `middleware`, `response_format`, `checkpointer` and the rest). It SHALL pass those to `create_agent` unchanged, except that the chat's tools are added to `tools`. A keyword argument `create_agent` does not accept MUST raise `TypeError` when the connector is created, naming that argument. The agent's own `name`, when not given, SHALL be the connector's name. Creating the connector MUST NOT call the model.

#### Scenario: Options reach create_agent
- **WHEN** a `BasicAgentConnector` is created with `system_prompt="Be brief."` and asked a question
- **THEN** the model receives "Be brief." as its system prompt

#### Scenario: An unknown option
- **WHEN** a `BasicAgentConnector` is created with `temprature=0.2`
- **THEN** creating it raises `TypeError` naming `temprature`

### Requirement: The model may be an Endpoint
`model` SHALL accept what `create_agent` accepts (a model name or a chat model) and also an `Endpoint`. An `Endpoint` MUST become an OpenAI-compatible chat model for its URL and model (`gpt-4o` when it has none), whose key is read from the endpoint's key source each time it is needed, never when the connector is created, and never stored as plain text on the connector. A key that cannot be read MUST become an `ERROR` reply naming the reason.

#### Scenario: Created without the key
- **WHEN** a `BasicAgentConnector` is created with an `Endpoint` whose key variable is not set
- **THEN** creating it succeeds, and the first question gets an `ERROR` reply saying the variable is not set

### Requirement: Packaged behind its own extra
`BasicAgentConnector` SHALL be importable from `chatinho.connectors.agents.basic`, `chatinho.connectors.agents`, `chatinho.connectors` and `chatinho`, and SHALL need the `langchain` extra. Importing `chatinho`, `chatinho.connectors` or `chatinho.connectors.agents` MUST NOT import LangChain. Reading `BasicAgentConnector` off `chatinho` without the extra MUST raise `ImportError` naming `chatinho[langchain]`. The former name `AgentConnector` MUST NOT be exported, and the module `chatinho.connectors.agent` MUST NOT exist.

#### Scenario: Without the extra
- **WHEN** LangChain is not installed and code reads `chatinho.BasicAgentConnector`
- **THEN** it raises `ImportError` naming `chatinho[langchain]`

#### Scenario: The core stays light
- **WHEN** code imports `chatinho`
- **THEN** no `langchain` module is imported

#### Scenario: The former name is gone
- **WHEN** code reads `chatinho.AgentConnector`
- **THEN** it raises `AttributeError`

### Requirement: Workspaces as tools
`BasicAgentConnector` SHALL declare `HookWorkspace` and SHALL take a `workspace` option, `False` by default. When it is created with `workspace=True` and its session has a workspace provider, the agent SHALL have, besides its other tools, one tool per operation of its own workspace, named `ws_` followed by the operation's name, described by the operation's description, and taking the operation's parameters. It SHALL also have one tool per read operation, named `ws_` followed by the operation's name and `_of`, that takes the name of the peer whose workspace it reads in a `workspace` parameter. The tools MUST be derived from the operations the provider's classes declare, so an operation a project adds becomes a tool with no change to the connector. A tool whose operation raises MUST return the failure as text naming the kind of error, never end the run. A `diff` result MUST become an attachment of the answer, as any tool's file does. A connector created without `workspace=True` MUST have no `ws_` tools and MUST NOT cause a workspace to be created. One whose session has no provider MUST have no `ws_` tools, MUST still answer, and SHALL log once that it has none.

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
