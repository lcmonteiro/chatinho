# key-sources Specification

## Purpose

Lets a program say where a key or token lives (environment, a `.env` file, a private file, the OS keychain, a password manager command) instead of passing its value, with one set of rules for reading, caching and reporting failures that never reveals the secret.

## Requirements

### Requirement: A key source yields a Secret
chatinho SHALL provide key sources that each read one secret when asked and return it as a `Secret`, with surrounding whitespace and a trailing newline removed. The sources MUST cover:
- the environment (`Env(name)`);
- a variable in a dotenv file (`DotEnv(path, name)`);
- a whole file (`File(path)`);
- the operating system's keychain (`Keyring(service, user)`);
- the standard output of a command (`Command(argv)`);
- a fixed value (`Literal(value)`);
- the first of several sources that yields a key (`Chain(*sources)`).

Reading an `Env`, `DotEnv` or `File` source MUST read the current value each time, so a rotated key is used without a restart. `Keyring` and `Command` sources MUST read once and reuse that value for the life of the source.

#### Scenario: From the environment
- **WHEN** `OPENAI_API_KEY` is `sk-env` and an `Env("OPENAI_API_KEY")` source is read
- **THEN** it yields a `Secret` revealing `sk-env`

#### Scenario: Rotated without a restart
- **WHEN** a `File` source is read, the file is rewritten with a new key, and the source is read again
- **THEN** the second read yields the new key

#### Scenario: A command runs once
- **WHEN** a `Command` source is read three times
- **THEN** the command ran once and all three reads yield its output, stripped of the trailing newline

#### Scenario: The first that yields
- **WHEN** `Chain(Env("MISSING"), File(path))` is read, `MISSING` is unset and the file holds a key
- **THEN** it yields the file's key

### Requirement: Failures name the reference, never the value
A source that cannot yield a key SHALL raise an error that names the source's reference and the reason. The reasons MUST include:
- the variable is unset or empty;
- the file is missing;
- the file is readable by other users;
- the keychain support is not installed;
- the keychain holds no such entry;
- the command failed or printed nothing.

`Chain` MUST raise only when every source failed, listing each reason. No error message MUST contain the value of any secret, including a value a command printed before failing.

#### Scenario: Unset variable
- **WHEN** `Env("OPENAI_API_KEY")` is read and the variable is unset
- **THEN** the error says `OPENAI_API_KEY` is not set

#### Scenario: Keychain support missing
- **WHEN** a `Keyring` source is read where the `keyring` extra is not installed
- **THEN** the error says to install `chatinho[keyring]`

#### Scenario: Every source failed
- **WHEN** `Chain(Env("A"), Env("B"))` is read and neither variable is set
- **THEN** the error names both `A` and `B`

### Requirement: A private key file must stay private
On systems with POSIX permissions, a `File` source SHALL refuse a file that its group or other users can read or write, and its error MUST name the file and the fix (`chmod 600`). A dotenv file is not checked, since such files are commonly shared with the project's other settings.

#### Scenario: Readable by others
- **WHEN** a `File` source is read and the file's mode is `0644`
- **THEN** it raises an error naming the file and `chmod 600`, and yields no key

### Requirement: Reference strings
chatinho SHALL parse a reference string into a key source, accepting these forms:
- `env:NAME`;
- `dotenv:PATH#NAME`, where `PATH` defaults to `.env` when only `#NAME` is given;
- `file:PATH`, where a leading `~` is expanded;
- `keyring:SERVICE/USER`;
- `cmd:COMMAND`, split like a shell command line and run without a shell;
- `literal:VALUE`.

A string with any other prefix, or none, MUST be refused with an error that lists the accepted prefixes, rather than being taken as a key.

#### Scenario: A keychain reference
- **WHEN** `keyring:chatinho/openai` is parsed
- **THEN** it reads the keychain entry with service `chatinho` and user `openai`

#### Scenario: A typo is not a key
- **WHEN** `evn:OPENAI_API_KEY` is parsed
- **THEN** it is refused, and the error lists the accepted prefixes

### Requirement: Accepted wherever a key or token is
Every argument that takes a key or a token SHALL accept a key source or a function returning a string, as well as a string:
- an endpoint's key (`Endpoint(api_key=...)`), and so an `OpenAIConnector`'s own key;
- MCP bearer tokens (`McpConnector(token=...)`, `McpFrontend(token=...)`, `build_mcp_session(token=...)`);
- delegated credentials (`McpConnector(delegate={...})`).

A plain string MUST keep meaning the value itself and MUST NOT be parsed as a reference. A server's token MUST be read when the frontend is created, so a missing token fails at startup.

#### Scenario: A plain string is the value
- **WHEN** an endpoint is created with `api_key="env:X"`
- **THEN** `env:X` itself is the key, and no variable is read

#### Scenario: A server token from a source
- **WHEN** `McpFrontend(token=Env("CHATINHO_MCP_TOKEN"))` is created with the variable set to `s3cret`
- **THEN** requests carrying `s3cret` are let in, and others are refused

#### Scenario: A missing server token fails at startup
- **WHEN** `McpFrontend(token=Env("UNSET"))` is created
- **THEN** creating it raises the source's error, naming `UNSET`
