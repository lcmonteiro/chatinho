## MODIFIED Requirements

### Requirement: The chat as tools
On a question, the agent SHALL have, besides its own tools:
- one tool per other peer that answers questions, named `ask_` followed by the peer's name, which asks that peer the text it is given and returns its answer as the peer's `Reply`, with its text and its status (`answered`, `asked` or `error`);
- one tool per command, named `run_` followed by the command's name and described by the command's description, which runs it with the arguments it is given and returns what it answered.

Characters a model API does not accept in a tool name MUST be replaced with `_`. The connector itself and the user MUST NOT be among the peers. With `ask_user=True`, a tool `ask_user` SHALL ask the user, wait for the answer and return it as the user's `Reply`. With `peers=` or `commands=`, only the names listed SHALL become tools. The tools SHALL reflect who is in the chat when the question is asked. A tool whose peer or command fails MUST NOT end the run: an `ask_` tool whose peer raises MUST return a `Reply` with status `error` naming the peer and the kind of failure, never the exception's message; a peer's own `error` reply MUST reach the agent as that `Reply`; and a `run_` tool whose command fails MUST return the failure as text. A peer asked through a tool MAY ask the connector back; how deep that goes is bounded by the session's `max_depth`.

#### Scenario: Asking another peer
- **WHEN** the chat has a peer `coder`, and the agent calls `ask_coder` with "Write a test"
- **THEN** `coder` is asked "Write a test", and its answer is the tool's result, as `coder`'s `Reply` with status `answered`

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
- **THEN** the tool returns a `Reply` with status `error` whose text names `coder` and the exception's type, and the agent still answers

#### Scenario: A peer's error reply
- **WHEN** the agent calls `ask_quota` and `quota` answers `Reply("quota exceeded", status="error")`
- **THEN** the tool returns that `Reply`, with text `quota exceeded` and status `error`, and the agent still answers

#### Scenario: Asked back
- **WHEN** the agent asks `coder`, and `coder` asks the agent before answering
- **THEN** the agent answers `coder`, `coder` answers the agent, and the agent answers the user
