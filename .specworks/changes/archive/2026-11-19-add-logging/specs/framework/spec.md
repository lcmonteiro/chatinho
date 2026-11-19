# Spec Delta: framework

## ADDED Requirements

### Requirement: REQ-CORE-034 A chat that runs writes a log file

`ChatSession.run()` SHALL, before it starts the session, send every record of the `chatinho` loggers, from DEBUG up, to the file `chatinho.<YYYY-MM-DD>.log` in the system's temporary directory, dated by the local day the file was first opened in the process and appended to. Each line MUST carry the time, the level, the process id and the logger's name. The file SHALL be opened once per process: a later `run()` in the same process MUST NOT write any record twice. Records of other libraries MUST NOT be written to it. Nothing but `run()` SHALL open it: importing chatinho, and driving a session with `start()` and `close()`, MUST NOT write any file. The program's own logging MUST receive chatinho's records exactly as it did before: no record it did not receive before, none it received before missing. Writing the file MUST NOT block the event loop. When the file cannot be opened, the chat MUST run anyway, and one line on stderr SHALL name the path and the reason.

#### Scenario: AC-CORE-034.1 The file and its lines

- **GIVEN** a session whose only peer serves, logs a DEBUG record on a `chatinho` logger and returns
- **WHEN** the session runs
- **THEN** `<tempdir>/chatinho.<today>.log` holds that record on one line with the time, `DEBUG`, the process id and the logger's name

#### Scenario: AC-CORE-034.2 Appended, never doubled

- **GIVEN** a log file for today that already holds a line
- **WHEN** two sessions run one after the other in the same process, each logging one record
- **THEN** the file still holds the earlier line, and each session's record appears exactly once

#### Scenario: AC-CORE-034.3 Only run opens it

- **WHEN** chatinho is imported and a session is started and closed by hand, logging a record
- **THEN** no log file is created in the temporary directory

#### Scenario: AC-CORE-034.4 Only chatinho's records

- **WHEN** a running session's peer logs one record on a `chatinho` logger and one on a logger of another name
- **THEN** the file holds the first and not the second

#### Scenario: AC-CORE-034.5 The program's own logging is unchanged

- **GIVEN** a program whose root logger has a handler at INFO
- **WHEN** a running session's peer logs a DEBUG and a WARNING record on a `chatinho` logger
- **THEN** the program's handler receives the WARNING and not the DEBUG record, and the file holds both

#### Scenario: AC-CORE-034.6 A directory that cannot be written

- **GIVEN** a temporary directory where the file cannot be created
- **WHEN** a session runs
- **THEN** its peers serve and it closes normally, and stderr holds one line naming the file's path

### Requirement: REQ-CORE-035 The session logs what happens in the chat

The session SHALL log, on the `chatinho` loggers, every event of the chat: each peer attached with its name and id, each command and role attached with its name; the session started, with how many messages were loaded, and closed; each message posted, with its id, sender, addressee, the message it replies to, its status, the length of its text and the number of its attachments; each ask's outcome, with the question's id and the answer's status, or that it failed or was cancelled; each command run, with its name and who ran it; each routing decision, with the message's id and the peer it went to or nobody; and each `forget`, with how many messages went. A failure SHALL keep being logged at WARNING or ERROR with its traceback; the other events SHALL be logged at DEBUG or INFO.

#### Scenario: AC-CORE-035.1 Attached and started

- **WHEN** a session with a peer named `bot` and a command named `upper` is started and closed
- **THEN** records name `bot` with its id, `upper`, the start with the number of messages loaded, and the close

#### Scenario: AC-CORE-035.2 A message posted

- **WHEN** a peer says a message replying to another
- **THEN** a record holds the new message's id, its sender's id, its addressee, the id it replies to, its status and the length of its text

#### Scenario: AC-CORE-035.3 An ask and its answer

- **WHEN** a peer asks another and gets an answer
- **THEN** a record holds the question's id and the answer's status

#### Scenario: AC-CORE-035.4 An ask that fails

- **WHEN** the asked peer's `answer` raises
- **THEN** an error record holds the traceback, and a record holds the question's id and the `error` status of its reply

#### Scenario: AC-CORE-035.5 A command run

- **WHEN** the user runs `/upper`
- **THEN** a record names `upper` and the id of who ran it

#### Scenario: AC-CORE-035.6 A routing decision

- **GIVEN** a session with one answering peer and a router
- **WHEN** the user says a message naming nobody
- **THEN** a record holds the message's id and the id of the peer it was routed to

#### Scenario: AC-CORE-035.7 Forgetting

- **WHEN** a session forgets messages
- **THEN** a record holds how many went

### Requirement: REQ-CORE-036 No record carries what was said or a key

No record the session writes SHALL hold the text of a message, the content of an attachment or the value of a credential, at any level. A failure's traceback is logged as it is: an exception's own message is the exception's, and the session MUST NOT add a message's text to it.

#### Scenario: AC-CORE-036.1 Nothing said reaches the log

- **GIVEN** a session capturing every `chatinho` record from DEBUG up
- **WHEN** a peer says a text, asks another with a second text and an attachment holding a third, the answer holds a fourth, and a message carries a credential
- **THEN** no captured record holds any of the four texts or the credential's value

#### Scenario: AC-CORE-036.2 A failure is still logged

- **WHEN** a peer that is asked raises
- **THEN** the error record holds the exception's type and traceback, and not the question's text
