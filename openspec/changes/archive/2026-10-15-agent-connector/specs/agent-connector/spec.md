# Spec Delta

## Purpose

Puts a LangChain agent into a chat as a peer: built from the same parameters as LangChain's `create_agent`, answering each question with one run of the agent, and given the chat itself as tools, so the agent can ask the other peers and run the chat's commands.

## ADDED Requirements

### Requirement: Built from create_agent's parameters
`AgentConnector` SHALL take its name in the chat, a `model` and `tools`, plus any other keyword argument `create_agent` accepts (`system_prompt`, `middleware`, `response_format`, `checkpointer` and the rest). It SHALL pass those to `create_agent` unchanged, except that the chat's tools are added to `tools`. A keyword argument `create_agent` does not accept MUST raise `TypeError` when the connector is created, naming that argument. The agent's own `name`, when not given, SHALL be the connector's name. Creating the connector MUST NOT call the model.

#### Scenario: Options reach create_agent
- **WHEN** an `AgentConnector` is created with `system_prompt="Be brief."` and asked a question
- **THEN** the model receives "Be brief." as its system prompt

#### Scenario: An unknown option
- **WHEN** an `AgentConnector` is created with `temprature=0.2`
- **THEN** creating it raises `TypeError` naming `temprature`

### Requirement: One question, one run of the agent
Each question the connector is asked SHALL run the agent once. The answer MUST be a `Reply` holding the text of the agent's last message; when that message's content is a list of blocks, the text blocks are joined. When `response_format` is set, the answer MUST be the structured response as JSON. Any failure of the run MUST become a reply with status `ERROR` naming the connector and the kind of failure, never an exception for whoever asked. Several questions MAY run at once, and none of them blocks the session.

#### Scenario: The last message is the answer
- **WHEN** the agent calls a tool and then answers "It is sunny."
- **THEN** the connector answers "It is sunny."

#### Scenario: A structured answer
- **WHEN** the connector has a `response_format` and the agent returns a structured response
- **THEN** the answer is that response as JSON

#### Scenario: The model fails
- **WHEN** the model raises while the agent runs
- **THEN** the answer is an `ERROR` reply naming the connector and the error's type

### Requirement: The chat as tools
On a question, the agent SHALL have, besides its own tools:
- one tool per other peer that answers questions, named `ask_` followed by the peer's name, which asks that peer the text it is given and returns its answer;
- one tool per command, named `run_` followed by the command's name and described by the command's description, which runs it with the arguments it is given and returns what it answered.

Characters a model API does not accept in a tool name MUST be replaced with `_`. The connector itself and the user MUST NOT be among the peers. With `ask_user=True`, a tool `ask_user` SHALL ask the user and wait for the answer. With `peers=` or `commands=`, only the names listed SHALL become tools. The tools SHALL reflect who is in the chat when the question is asked. A tool whose peer or command fails MUST return the failure as text to the agent rather than end the run. A peer asked through a tool MAY ask the connector back; how deep that goes is bounded by the session's `max_depth`.

#### Scenario: Asking another peer
- **WHEN** the chat has a peer `coder`, and the agent calls `ask_coder` with "Write a test"
- **THEN** `coder` is asked "Write a test", and its answer is the tool's result

#### Scenario: Running a command
- **WHEN** the chat has a command `help`, and the agent calls `run_help`
- **THEN** `/help` runs, and what it answered is the tool's result

#### Scenario: Never itself, never the user by default
- **WHEN** the agent is asked a question in a chat with the user, the connector and one other peer `coder`
- **THEN** its chat tools are `ask_coder` and one `run_` tool per command, with no tool for itself and no `ask_user`

#### Scenario: Limited to the listed peers
- **WHEN** the connector is created with `peers=["coder"]` in a chat with peers `coder` and `lab`
- **THEN** the agent has `ask_coder` and no `ask_lab`

#### Scenario: A peer joins later
- **WHEN** a peer `lab` is added after the agent has answered once, and the agent is asked again
- **THEN** the agent has `ask_lab` for the second question

#### Scenario: A failing peer
- **WHEN** the agent calls `ask_coder` and `coder` raises
- **THEN** the tool returns text saying `coder` failed, and the agent still answers

#### Scenario: Asked back
- **WHEN** the agent asks `coder`, and `coder` asks the agent before answering
- **THEN** the agent answers `coder`, `coder` answers the agent, and the agent answers the user

### Requirement: Memory comes from the chat
Before the question, the agent SHALL be given the messages `context()` returns for the connector's `memory` query, oldest first, with the same default as the OpenAI connector (what passed between it and anyone, without errors, the last twenty). Its own messages MUST be assistant messages, the user's MUST be user messages, and other peers' MUST be user messages prefixed with the peer's name. The questions it asked through its tools, and their answers, MUST be left out. When a `checkpointer` is given, each question MUST run on its own thread (the question's id), never on a thread shared by several questions.

#### Scenario: It remembers the conversation
- **WHEN** the user tells the agent "My name is Ana" and then asks "What is my name?"
- **THEN** the second run receives the first question and its answer before the new question

#### Scenario: Its tool calls are not memory
- **WHEN** the agent asked `coder` through a tool while answering the first question
- **THEN** the second run's history holds the first question and answer, not the ask to `coder`

#### Scenario: One thread per question
- **WHEN** the connector has a checkpointer and is asked two questions
- **THEN** the two runs use two different thread ids

### Requirement: The model may be an Endpoint
`model` SHALL accept what `create_agent` accepts (a model name or a chat model) and also an `Endpoint`. An `Endpoint` MUST become an OpenAI-compatible chat model for its URL and model (`gpt-4o` when it has none), whose key is read from the endpoint's key source each time it is needed, never when the connector is created, and never stored as plain text on the connector. A key that cannot be read MUST become an `ERROR` reply naming the reason.

#### Scenario: Created without the key
- **WHEN** an `AgentConnector` is created with an `Endpoint` whose key variable is not set
- **THEN** creating it succeeds, and the first question gets an `ERROR` reply saying the variable is not set

### Requirement: Packaged behind its own extra
`AgentConnector` SHALL be importable from `chatinho.connectors.agent`, `chatinho.connectors` and `chatinho`, and SHALL need the `langchain` extra. Importing `chatinho` or `chatinho.connectors` MUST NOT import LangChain. Reading `AgentConnector` off `chatinho` without the extra MUST raise `ImportError` naming `chatinho[langchain]`.

#### Scenario: Without the extra
- **WHEN** LangChain is not installed and code reads `chatinho.AgentConnector`
- **THEN** it raises `ImportError` naming `chatinho[langchain]`

#### Scenario: The core stays light
- **WHEN** code imports `chatinho`
- **THEN** no `langchain` module is imported
