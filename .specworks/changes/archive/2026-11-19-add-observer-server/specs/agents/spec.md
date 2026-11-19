# Spec Delta: agents

## ADDED Requirements

### Requirement: REQ-AGENT-012 An agent traces its run

`AgentPeer` SHALL declare `HookTrace` and trace each step of a run on the message it answers or responds to: each node of its graph (`extract`, `agent`, `verify`, `load`), each model call and each tool call. A step SHALL be traced when it starts, with state `running`, and when it ends, with state `done` or `error`; the end follows the start. A step's start follows the step it ran in when it is the first inside it, and otherwise the last step that ended inside the same one; steps started from the same point (tool calls of one model call) follow the same trace. The text names the step: the node's name, `model <name>`, or `tool <name>` with its input, and on its end the output or the error's type, cut short.

#### Scenario: AC-AGENT-012.1 The nodes of a run

- **GIVEN** an agent peer with a scripted model that answers without tools, in a session with a recorder
- **WHEN** the peer is asked a question
- **THEN** the recorder holds a `running` and a `done` trace for each of `extract`, `agent`, `verify` and `load`, all for the question's id, each `done` following its `running`

#### Scenario: AC-AGENT-012.2 A tool call

- **GIVEN** a scripted model that calls one tool and then answers
- **WHEN** the peer is asked
- **THEN** there is a `tool <name>` start trace whose text holds the tool's input, following the end of the model call that asked for it, and an end trace holding its output

#### Scenario: AC-AGENT-012.3 Two tool calls at once

- **GIVEN** a scripted model that calls two tools in one turn
- **WHEN** the peer is asked
- **THEN** both tools' start traces follow the same trace

#### Scenario: AC-AGENT-012.4 A step that fails

- **GIVEN** a tool that raises
- **WHEN** the model calls it
- **THEN** that tool's end trace has state `error` and its text names the error's type

#### Scenario: AC-AGENT-012.5 Tracing never fails the run

- **GIVEN** a recorder whose `record` raises
- **WHEN** the peer is asked
- **THEN** it answers as it does with no recorder

#### Scenario: AC-AGENT-012.6 Each run is its own graph

- **WHEN** the peer is asked two questions at once
- **THEN** each question's traces follow only traces of the same question
