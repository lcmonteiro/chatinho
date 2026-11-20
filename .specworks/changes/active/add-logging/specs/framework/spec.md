# Spec Delta: framework

## MODIFIED Requirements

### Requirement: REQ-CORE-034 A chat that runs writes a log file when asked to

`ChatSession.run()` SHALL, before it starts the session, read the environment variable `CHATINHO_LOG_PATH`. When it is unset or empty, `run()` MUST NOT write any file and MUST NOT change any logging configuration. When it names a directory, `run()` SHALL send every record of the `chatinho` loggers, from DEBUG up, to the file `chatinho.<YYYY-MM-DD>.log` in that directory, dated by the local day the file was first opened in the process and appended to. A directory that does not exist SHALL be created, accessible to its owner only; a file `run()` creates SHALL be readable and writable by its owner only, and a file that already exists MUST keep its mode. Each line MUST carry the time, the level, the process id and the logger's name. The file SHALL be opened once per process: a later `run()` in the same process MUST NOT write any record twice. Records of other libraries MUST NOT be written to it. Nothing but `run()` SHALL open it: importing chatinho, and driving a session with `start()` and `close()`, MUST NOT write any file whatever the variable says. The program's own logging MUST receive chatinho's records exactly as it did before: no record it did not receive before, none it received before missing. Writing the file MUST NOT block the event loop. When the directory cannot be created or the file cannot be opened, the chat MUST run anyway, and one line on stderr SHALL name the path and the reason.

#### Scenario: AC-CORE-034.1 The file and its lines

- **GIVEN** `CHATINHO_LOG_PATH` names a directory, and a session whose only peer serves, logs a DEBUG record on a `chatinho` logger and returns
- **WHEN** the session runs
- **THEN** `<directory>/chatinho.<today>.log` holds that record on one line with the time, `DEBUG`, the process id and the logger's name

#### Scenario: AC-CORE-034.2 Appended, never doubled

- **GIVEN** `CHATINHO_LOG_PATH` names a directory holding today's log file with one line
- **WHEN** two sessions run one after the other in the same process, each logging one record
- **THEN** the file still holds the earlier line, and each session's record appears exactly once

#### Scenario: AC-CORE-034.3 Only run opens it

- **GIVEN** `CHATINHO_LOG_PATH` names a directory
- **WHEN** chatinho is imported and a session is started and closed by hand, logging a record
- **THEN** no log file is created in that directory

#### Scenario: AC-CORE-034.4 Only chatinho's records

- **GIVEN** `CHATINHO_LOG_PATH` names a directory
- **WHEN** a running session's peer logs one record on a `chatinho` logger and one on a logger of another name
- **THEN** the file holds the first and not the second

#### Scenario: AC-CORE-034.5 The program's own logging is unchanged

- **GIVEN** `CHATINHO_LOG_PATH` names a directory, and a program whose root logger has a handler at INFO
- **WHEN** a running session's peer logs a DEBUG and a WARNING record on a `chatinho` logger
- **THEN** the program's handler receives the WARNING and not the DEBUG record, and the file holds both

#### Scenario: AC-CORE-034.6 A directory that cannot be written

- **GIVEN** `CHATINHO_LOG_PATH` names a path that is a regular file, so no directory can be made there
- **WHEN** a session runs
- **THEN** its peers serve and it closes normally, and stderr holds one line naming the log file's path

#### Scenario: AC-CORE-034.7 Unset, logging is off

- **GIVEN** `CHATINHO_LOG_PATH` is not set
- **WHEN** a session whose peer logs a record runs
- **THEN** no log file is created in the temporary directory, and the `chatinho` logger's level, handlers and propagation are the same after the run as before it

#### Scenario: AC-CORE-034.8 Empty is unset

- **GIVEN** `CHATINHO_LOG_PATH` is set to an empty string
- **WHEN** a session runs
- **THEN** no log file is created, as when the variable is unset

#### Scenario: AC-CORE-034.9 A missing directory is made for its owner

- **GIVEN** `CHATINHO_LOG_PATH` names a directory that does not exist
- **WHEN** a session runs
- **THEN** the directory exists, accessible to its owner only, and holds today's log file, readable and writable by its owner only

#### Scenario: AC-CORE-034.10 An existing file keeps its mode

- **GIVEN** `CHATINHO_LOG_PATH` names a directory holding today's log file with mode 0640
- **WHEN** a session runs
- **THEN** the file's mode is still 0640, and the run's records were appended to it
