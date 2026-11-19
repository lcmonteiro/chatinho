# Spec Delta: framework

## ADDED Requirements

### Requirement: REQ-CORE-030 A peer traces the steps of a message

A peer or command that declares `HookTrace` SHALL be granted `trace(msg_id, state, text, prev=None)`, a coroutine that records one step of processing the message `msg_id` and returns the new trace's id. The trace SHALL hold its own id (unique across sessions, `trc-` and 16 hex characters as text), the message id, the state, the id of the trace it follows (or none), the text, the id of who traced it (`TOOL` for a command) and when. The state MUST be one of `running`, `done` and `error`, given as the state or its name. Text longer than `TRACE_TEXT_LIMIT` (2000 characters) MUST be cut to it, ending with `…`.

#### Scenario: AC-CORE-030.1 A trace is recorded

- **GIVEN** a session with a backend that declares `HookRecord`, and a peer that declares `HookTrace`
- **WHEN** the peer traces message `m` with state `running` and text `extract`
- **THEN** it gets back a trace id, and the backend's `record` is given one trace with that id, message `m`, state `running`, text `extract`, no `prev`, the peer's id as `frm` and a timestamp

#### Scenario: AC-CORE-030.2 One trace follows another

- **WHEN** a peer traces `t1` and then a second trace with `prev=t1`
- **THEN** the second trace recorded has `prev` equal to `t1`

#### Scenario: AC-CORE-030.3 The state by its name

- **WHEN** a peer traces with the state given as `"done"`
- **THEN** the recorded trace's state is `done`

#### Scenario: AC-CORE-030.4 An unknown state

- **WHEN** a peer traces with the state `"finished"`
- **THEN** `trace` raises `ValueError` naming the states it takes, and nothing is recorded

#### Scenario: AC-CORE-030.5 A long text is cut

- **WHEN** a peer traces a text of 5000 characters
- **THEN** the recorded text is `TRACE_TEXT_LIMIT` characters long and ends with `…`

#### Scenario: AC-CORE-030.6 A command traces as TOOL

- **WHEN** a command that declares `HookTrace` traces while it runs
- **THEN** the recorded trace's `frm` is `TOOL`

#### Scenario: AC-CORE-030.7 Not a message id

- **WHEN** a peer traces with a plain string as `msg_id`
- **THEN** `trace` raises `TypeError`, and nothing is recorded

### Requirement: REQ-CORE-031 A trace follows only a trace the session made

`trace` MUST refuse a `prev` that is not the id of a trace this session returned: it raises `ValueError` and records nothing. A trace id read back from elsewhere is not known to the session.

#### Scenario: AC-CORE-031.1 An unknown prev

- **WHEN** a peer traces with `prev` set to a trace id the session never returned
- **THEN** `trace` raises `ValueError`, and nothing is recorded

#### Scenario: AC-CORE-031.2 Another peer's trace

- **GIVEN** peer A traced `t1`
- **WHEN** peer B traces with `prev=t1`
- **THEN** the trace is recorded with `prev` equal to `t1`

### Requirement: REQ-CORE-032 Traces go to the recorder and nowhere else

The session SHALL hand every trace to the first peer that declares `HookRecord`, awaiting its `record` before `trace` returns. With no recorder the trace MUST be dropped and its id still returned. A recorder that raises MUST be logged and the id still returned: a broken store never fails the step being traced. A trace MUST NOT be a message: no peer hears it, nobody answers it, `context()` never returns it, and the message store does not hold it.

#### Scenario: AC-CORE-032.1 No recorder

- **GIVEN** a session where no peer declares `HookRecord`
- **WHEN** a peer traces
- **THEN** it gets back a trace id, and nothing fails

#### Scenario: AC-CORE-032.2 The recorder raises

- **GIVEN** a recorder whose `record` raises
- **WHEN** a peer traces
- **THEN** it gets back a trace id, and the failure is logged as an error

#### Scenario: AC-CORE-032.3 A trace is not heard

- **GIVEN** a peer that declares `HookListen`, and a recorder
- **WHEN** another peer traces a step of a message
- **THEN** the listener hears no trace, and `context()` returns the same messages as before the trace

#### Scenario: AC-CORE-032.4 A recorder is not addressed

- **WHEN** the recorder is also a peer that declares `HookListen`
- **THEN** it hears the messages as before, and receives traces only through `record`

### Requirement: REQ-CORE-033 Trace names are public

`ChatTrace`, `TraceID`, `TraceState`, `TRACE_TEXT_LIMIT`, `HookTrace`, `HookRecord` and the grant protocol `Trace` SHALL be importable from `chatinho` and need no extra. `HookTrace` grants only `trace`, and `HookRecord` demands only `record`.

#### Scenario: AC-CORE-033.1 The names off the package

- **WHEN** the trace names are read off `chatinho` in a process where no extra's library can be imported
- **THEN** each one is found

#### Scenario: AC-CORE-033.2 A recorder without record

- **WHEN** a class without a `record` method declares `HookRecord`
- **THEN** the declaration raises `TypeError` naming `record`
