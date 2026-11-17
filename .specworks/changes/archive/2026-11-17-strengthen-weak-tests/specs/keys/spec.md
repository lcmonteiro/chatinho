# Spec Delta: keys

## MODIFIED Requirements

### Requirement: REQ-KEYS-003 A failure names the reference, never the value

A source that cannot yield a key SHALL raise `KeyUnavailable` naming the source's reference and the reason: the variable is unset, the dotenv file has no such variable, the file does not exist, the command failed or its program is not installed, the keychain support is not installed, or the keychain has no such entry. No error message MUST contain the value of a secret, including what a command printed before failing.

#### Scenario: AC-KEYS-003.1 An unset variable

- **WHEN** `Env("OPENAI_API_KEY")` is read and the variable is unset
- **THEN** the error says `OPENAI_API_KEY is not set`

#### Scenario: AC-KEYS-003.2 A variable the dotenv file lacks

- **WHEN** `DotEnv` reads a variable the file does not set
- **THEN** the error names the variable and the file's path

#### Scenario: AC-KEYS-003.3 A missing file

- **WHEN** a `File` source is read and the file does not exist
- **THEN** the error says it does not exist

#### Scenario: AC-KEYS-003.4 A failing command hides its output

- **GIVEN** a command that prints `sk-partial` and exits with status 3
- **WHEN** its `Command` source is read
- **THEN** the error says it exited 3 and does not contain `sk-partial`

#### Scenario: AC-KEYS-003.5 A missing program

- **WHEN** a `Command` source names a program that is not installed
- **THEN** the error says it is not installed

#### Scenario: AC-KEYS-003.6 Keychain support missing

- **WHEN** a `Keyring` source is read where the `keyring` library cannot be imported
- **THEN** the error says to install `chatinho[keyring]`

#### Scenario: AC-KEYS-003.7 No such keychain entry

- **WHEN** a `Keyring("chatinho", "openai")` source is read and the keychain holds no such entry
- **THEN** the error says `chatinho/openai: no such entry`

### Requirement: REQ-KEYS-006 Reference strings

`key(reference)` SHALL parse a reference string into a key source: `env:NAME`; `dotenv:PATH#NAME`, where the path defaults to `.env`; `file:PATH`, with a leading `~` expanded; `keyring:SERVICE/USER`; `cmd:COMMAND`, split like a shell command line; and `literal:VALUE`. A string with any other prefix, with none, or with an incomplete reference MUST be refused with `ValueError` listing the accepted prefixes, without repeating the string.

#### Scenario: AC-KEYS-006.1 Each form

- **WHEN** `env:OPENAI_API_KEY`, `dotenv:conf/.env#KEY`, `dotenv:#KEY`, `keyring:chatinho/openai` and `cmd:pass show 'api/open ai'` are parsed
- **THEN** each gives the source of its kind with those fields: the dotenv sources read `conf/.env` and `.env`, and the command is split into `pass`, `show` and `api/open ai`

#### Scenario: AC-KEYS-006.2 Defaults, the home folder and a literal

- **WHEN** `dotenv:#KEY`, `file:~/k` and `literal:ollama` are parsed
- **THEN** the first reads `.env`, the second's path has `~` expanded, and the third yields `ollama`

#### Scenario: AC-KEYS-006.3 A typo is not a key

- **WHEN** `evn:OPENAI_API_KEY`, `sk-abcdef`, `keyring:only` or `env:` is parsed
- **THEN** `ValueError` is raised listing the accepted prefixes, and `sk-abcdef` is not in the message

