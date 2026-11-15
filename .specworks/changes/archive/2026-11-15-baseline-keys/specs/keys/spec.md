# Spec Delta: keys

## Purpose

Lets a program say where a key or token lives instead of passing its value, and treats an OpenAI-compatible endpoint, its model and its key as one named profile. It has no living spec yet; this records the behaviour it already has.

## ADDED Requirements

### Requirement: REQ-KEYS-001 A key source yields a Secret

The system SHALL provide key sources that each read one secret when asked and return it as a `Secret`, with surrounding whitespace removed: the environment (`Env(name)`), a variable in a dotenv file (`DotEnv(path, name)`), a whole file (`File(path)`) and a fixed value (`Literal(value)`). `Env`, `DotEnv` and `File` MUST read the current value each time, so a rotated key is used without a restart. A `Literal` MUST NOT show its value in its `repr`.

#### Scenario: AC-KEYS-001.1 From the environment

- **GIVEN** `OPENAI_API_KEY` holds `sk-env` with a space before and a newline after
- **WHEN** `Env("OPENAI_API_KEY")` is read
- **THEN** it yields a `Secret` revealing `sk-env`

#### Scenario: AC-KEYS-001.2 A dotenv variable

- **GIVEN** a dotenv file with a comment, an `export` line, a quoted value and a value followed by a comment
- **WHEN** `DotEnv` reads the quoted variable and the commented one
- **THEN** each yields its value without the quotes or the comment

#### Scenario: AC-KEYS-001.3 Rotated without a restart

- **GIVEN** a `File` source that was read once
- **WHEN** the file is rewritten with a new key and the source is read again
- **THEN** the second read yields the new key

#### Scenario: AC-KEYS-001.4 A literal never shows

- **WHEN** the `repr` of `Literal("sk-lit")` is taken
- **THEN** `sk-lit` is not in it

### Requirement: REQ-KEYS-002 Commands and the keychain read once

The system SHALL provide `Command(argv)`, which yields the standard output of a command run without a shell, and `Keyring(service, user)`, which yields an entry of the operating system's keychain. Each MUST read once and reuse that value for the life of the source.

#### Scenario: AC-KEYS-002.1 A command runs once

- **WHEN** a `Command` source is read three times
- **THEN** the command ran once and all three reads yield its output without the trailing newline

#### Scenario: AC-KEYS-002.2 The keychain is read once

- **WHEN** a `Keyring("chatinho", "openai")` source is read twice
- **THEN** the keychain was asked once, for service `chatinho` and user `openai`, and both reads yield its entry

### Requirement: REQ-KEYS-003 A failure names the reference, never the value

A source that cannot yield a key SHALL raise `KeyUnavailable` naming the source's reference and the reason: the variable is unset, the dotenv file has no such variable, the file does not exist, the command failed or its program is not installed, the keychain support is not installed, or the keychain has no such entry. No error message MUST contain the value of a secret, including what a command printed before failing.

#### Scenario: AC-KEYS-003.1 An unset variable

- **WHEN** `Env("OPENAI_API_KEY")` is read and the variable is unset
- **THEN** the error says `OPENAI_API_KEY is not set`

#### Scenario: AC-KEYS-003.2 A variable the dotenv file lacks

- **WHEN** `DotEnv` reads a variable the file does not set
- **THEN** the error names the variable and the file

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

### Requirement: REQ-KEYS-004 A private key file must stay private

On systems with POSIX permissions, a `File` source SHALL refuse a file that its group or other users can read or write. The error MUST name the file and the fix (`chmod 600`) and MUST NOT contain the key.

#### Scenario: AC-KEYS-004.1 Readable by others

- **GIVEN** a key file with mode `0644`
- **WHEN** its `File` source is read
- **THEN** `KeyUnavailable` is raised naming the file and `chmod 600`, without the key

### Requirement: REQ-KEYS-005 A chain yields the first key

`Chain(*sources)` SHALL read its sources in order and yield the first key any of them yields. It MUST raise `KeyUnavailable` only when every source failed, listing each reason.

#### Scenario: AC-KEYS-005.1 The first that yields

- **GIVEN** `MISSING` is unset and a private file holds a key
- **WHEN** `Chain(Env("MISSING"), File(path))` is read
- **THEN** it yields the file's key

#### Scenario: AC-KEYS-005.2 Every source failed

- **WHEN** `Chain(Env("A"), Env("B"))` is read and neither variable is set
- **THEN** the error says both that `A` is not set and that `B` is not set

### Requirement: REQ-KEYS-006 Reference strings

`key(reference)` SHALL parse a reference string into a key source: `env:NAME`; `dotenv:PATH#NAME`, where the path defaults to `.env`; `file:PATH`, with a leading `~` expanded; `keyring:SERVICE/USER`; `cmd:COMMAND`, split like a shell command line; and `literal:VALUE`. A string with any other prefix, with none, or with an incomplete reference MUST be refused with `ValueError` listing the accepted prefixes, without repeating the string.

#### Scenario: AC-KEYS-006.1 Each form

- **WHEN** `env:OPENAI_API_KEY`, `dotenv:conf/.env#KEY`, `dotenv:#KEY`, `keyring:chatinho/openai` and `cmd:pass show 'api/open ai'` are parsed
- **THEN** each gives the source of its kind with those fields, the command split into `pass`, `show` and `api/open ai`

#### Scenario: AC-KEYS-006.2 Defaults, the home folder and a literal

- **WHEN** `dotenv:#KEY`, `file:~/k` and `literal:ollama` are parsed
- **THEN** the first reads `.env`, the second's path has `~` expanded, and the third yields `ollama`

#### Scenario: AC-KEYS-006.3 A typo is not a key

- **WHEN** `evn:OPENAI_API_KEY`, `sk-abcdef`, `keyring:only` or `env:` is parsed
- **THEN** `ValueError` is raised listing the accepted prefixes, and `sk-abcdef` is not in the message

### Requirement: REQ-KEYS-007 Whatever a key argument is given becomes a source

`to_source(value)` SHALL turn what a key or token argument was given into a key source: a key source as it is, a string or a `Secret` as the value itself, a function as a source that calls it on each read, and `None` as `None`; anything else MUST raise `TypeError`. A plain string MUST NOT be parsed as a reference. `read_async(source)` SHALL read a source without blocking the event loop.

#### Scenario: AC-KEYS-007.1 A plain string is the value

- **GIVEN** the variable `X` is set
- **WHEN** `to_source("env:X")` is read
- **THEN** it yields `env:X` itself

#### Scenario: AC-KEYS-007.2 A function, a Secret, nothing, and something else

- **WHEN** `to_source` is given a function, a `Secret`, `None` and the number 42
- **THEN** the first two read as their values, the third is `None`, and the fourth raises `TypeError`

#### Scenario: AC-KEYS-007.3 Read from a coroutine

- **WHEN** `read_async` is awaited on an `Env` source and on a `Command` source
- **THEN** each yields its key

### Requirement: REQ-KEYS-008 An endpoint bundles URL, model and key

`Endpoint` SHALL be an immutable value holding an optional `base_url`, an optional `model`, an optional `api_key` kept as a key source (a string given is the key itself), and the name of the profile it came from. `with_model(model)` and `without_key()` MUST return copies differing only in that field. Showing an endpoint MUST NOT reveal its key.

#### Scenario: AC-KEYS-008.1 Another model, same provider

- **GIVEN** an endpoint for `https://example/v1` with model `gpt-4o-mini`
- **WHEN** `with_model("gpt-4o")` and `without_key()` are called
- **THEN** the first copy has model `gpt-4o` with the same URL and key source, the second has no key, and the original is unchanged

#### Scenario: AC-KEYS-008.2 Never shows the key

- **WHEN** an endpoint whose key is `Literal("sk-1")` is shown
- **THEN** neither `sk-1` nor `api_key` appears

#### Scenario: AC-KEYS-008.3 A string key is the value

- **WHEN** endpoints are created with `api_key="env:X"`, with a function, and with no key
- **THEN** the first's key reads `env:X`, the second's reads what the function returns, and the third has no key

### Requirement: REQ-KEYS-009 Profiles file

The system SHALL read endpoint profiles from a TOML file: an optional top-level `default` naming a profile, and one table per profile, which MAY set `base_url`, `model` and `api_key` as a reference string. Any other field, or an `api_key` that is not a valid reference, MUST be refused with `ValueError` naming it. The file is the first that exists of the path in `CHATINHO_PROFILES`, `.chatinho.toml` in the current directory, and `chatinho/profiles.toml` under `$XDG_CONFIG_HOME` (or `~/.config`). On systems with POSIX permissions, a profiles file that group or other users can write MUST be refused with `ValueError` naming the file.

#### Scenario: AC-KEYS-009.1 A profile with a key reference

- **GIVEN** a profile `nvidia` with a URL, a model and `api_key = "env:ORBE_OPENAI_API_KEY"`
- **WHEN** it is loaded
- **THEN** the endpoint has that URL, model and profile name, and its key reads the variable

#### Scenario: AC-KEYS-009.2 The project's file wins

- **GIVEN** the user's `profiles.toml` and a `.chatinho.toml` in the current directory
- **WHEN** a profile is loaded
- **THEN** profiles come from `.chatinho.toml` only

#### Scenario: AC-KEYS-009.3 A misspelled field

- **WHEN** a profile `x` sets `modle`
- **THEN** loading it raises `ValueError` naming the field and the profile

#### Scenario: AC-KEYS-009.4 A bad key reference

- **WHEN** a profile sets `api_key = "evn:K"`
- **THEN** loading it raises `ValueError` naming `api_key`

#### Scenario: AC-KEYS-009.5 Writable by others

- **WHEN** the profiles file's mode is `0666`
- **THEN** loading any profile raises `ValueError` naming the file

### Requirement: REQ-KEYS-010 Choosing the profile

`Endpoint.load(profile=None)` SHALL choose the profile by its argument, else `CHATINHO_PROFILE`, else the file's `default`. A chosen profile the file does not have MUST raise `ValueError` listing the profiles it has; a profile chosen while no profiles file exists MUST raise `ValueError` naming the places searched. `CHATINHO_MODEL` and `CHATINHO_BASE_URL`, when set, MUST replace the profile's model and URL. When no profile is chosen, the endpoint MUST come from the environment: the key from `OPENAI_API_KEY`, the URL from `OPENAI_BASE_URL` and the model from `CHATINHO_MODEL`.

#### Scenario: AC-KEYS-010.1 The default profile

- **GIVEN** a file whose `default` is `nvidia`
- **WHEN** `Endpoint.load()` is called
- **THEN** it gives the `nvidia` profile

#### Scenario: AC-KEYS-010.2 Chosen by the environment, and the argument wins

- **GIVEN** `CHATINHO_PROFILE=local` and a file whose `default` is `nvidia`
- **WHEN** `Endpoint.load()` and `Endpoint.load("nvidia")` are called
- **THEN** the first gives `local` and the second `nvidia`

#### Scenario: AC-KEYS-010.3 Overriding fields

- **GIVEN** `CHATINHO_MODEL` and `CHATINHO_BASE_URL` are set
- **WHEN** a profile is loaded
- **THEN** the endpoint has that model and URL, and the profile's key

#### Scenario: AC-KEYS-010.4 An unknown profile

- **WHEN** `Endpoint.load("nvdia")` is called and the file has `local` and `nvidia`
- **THEN** `ValueError` is raised naming `nvdia` and listing `local, nvidia`

#### Scenario: AC-KEYS-010.5 A profile but no file

- **WHEN** `CHATINHO_PROFILE=nvidia` and no profiles file exists
- **THEN** `Endpoint.load()` raises `ValueError` naming `nvidia` and where it searched

#### Scenario: AC-KEYS-010.6 No profiles file

- **GIVEN** no profiles file, with `OPENAI_API_KEY`, `OPENAI_BASE_URL` and `CHATINHO_MODEL` set
- **WHEN** `Endpoint.load()` is called
- **THEN** the endpoint has that URL and model, no profile name, and its key reads `OPENAI_API_KEY`

### Requirement: REQ-KEYS-011 From prefixed environment variables

`Endpoint.from_env(prefix)` SHALL build an endpoint whose key is read from `<prefix>_API_KEY` when needed, with the URL in `<prefix>_BASE_URL` and the model in `<prefix>_MODEL`. The URL and model MUST be left unset when their variables are unset or empty.

#### Scenario: AC-KEYS-011.1 A custom prefix

- **GIVEN** `ORBE_OPENAI_API_KEY`, `ORBE_OPENAI_BASE_URL` and `ORBE_OPENAI_MODEL` are set
- **WHEN** `Endpoint.from_env("ORBE_OPENAI")` is called, and again with the model empty and the URL unset
- **THEN** the first has that URL, model and key, and the second has neither URL nor model

### Requirement: REQ-KEYS-012 Checking at startup

`Endpoint.check()` SHALL read the key once and raise the key source's `KeyUnavailable` when it cannot be read, without contacting the endpoint. An endpoint without a key source MUST raise `KeyUnavailable` saying no API key is configured.

#### Scenario: AC-KEYS-012.1 A missing key found early

- **WHEN** `check()` is called on an endpoint whose key reads an unset `OPENAI_API_KEY`, and on an endpoint with no key
- **THEN** the first raises an error naming `OPENAI_API_KEY`, and the second one saying there is no API key
