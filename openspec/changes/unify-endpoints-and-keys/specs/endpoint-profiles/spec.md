## Purpose

Treats an OpenAI-compatible endpoint, its default model and its key as one named profile, chosen at run time, so the same program can switch provider or model without code changes and a wrong combination is reported in one place.

## ADDED Requirements

### Requirement: An endpoint bundles URL, model and key
chatinho SHALL provide `Endpoint`, an immutable value holding:
- an optional `base_url`;
- an optional `model`;
- an optional key source for `api_key`;
- the name of the profile it came from, if any.

`with_model(model)` and `without_key()` MUST return copies differing only in that field. Showing an endpoint MUST NOT reveal its key.

#### Scenario: Another model, same provider
- **WHEN** `with_model("gpt-4o")` is called on an endpoint for `https://example/v1` with model `gpt-4o-mini`
- **THEN** the copy has model `gpt-4o`, the same URL and the same key source, and the original is unchanged

#### Scenario: Never shows the key
- **WHEN** an endpoint whose key source is `Literal("sk-1")` is printed
- **THEN** `sk-1` appears nowhere in the output

### Requirement: Profiles file
chatinho SHALL read profiles from a TOML file. The file MAY name a `default` profile at top level; each other top-level table is a profile. A profile MAY set:
- `base_url`;
- `model`;
- `api_key`, as a reference string.

Any other key in a profile MUST be refused with an error naming the key and the profile. The file MUST be the first that exists of:
1. the path in `CHATINHO_PROFILES`;
2. `.chatinho.toml` in the current directory;
3. `chatinho/profiles.toml` under `$XDG_CONFIG_HOME`, or under `~/.config` when that is unset.

On systems with POSIX permissions, a profiles file that group or other users can write MUST be refused, since a profile may name a command to run.

#### Scenario: A profile with a key reference
- **WHEN** the profiles file's `nvidia` profile sets `base_url`, `model`, and `api_key = "env:ORBE_OPENAI_API_KEY"`
- **THEN** loading `nvidia` gives an endpoint with that URL and model, whose key is read from `ORBE_OPENAI_API_KEY` when needed

#### Scenario: The project's file wins
- **WHEN** both `.chatinho.toml` in the current directory and the user's `profiles.toml` exist
- **THEN** profiles are read from `.chatinho.toml` only

#### Scenario: A misspelled field
- **WHEN** a profile sets `modle = "x"`
- **THEN** loading it fails with an error naming `modle` and the profile

#### Scenario: Writable by others
- **WHEN** the profiles file's mode is `0666`
- **THEN** loading any profile fails with an error naming the file

### Requirement: Choosing the profile, and overriding fields
`Endpoint.load(profile=None)` SHALL choose the profile by:
1. the argument;
2. else `CHATINHO_PROFILE`;
3. else the file's `default`.

A chosen profile that the file does not have MUST fail with an error listing the profiles it has. A profile chosen while no profiles file exists MUST fail with an error naming the places searched, rather than being ignored. After the profile is read, `CHATINHO_MODEL` and `CHATINHO_BASE_URL`, when set, MUST replace its model and URL.

When no profile is chosen (no argument, no `CHATINHO_PROFILE`, and no profiles file or no `default` in it), the endpoint MUST come from the environment instead:
- the key is read from `OPENAI_API_KEY`;
- the URL comes from `OPENAI_BASE_URL`;
- the model comes from `CHATINHO_MODEL`.

#### Scenario: Chosen by the environment
- **WHEN** `CHATINHO_PROFILE=local` and the file has `local` and `default = "nvidia"`
- **THEN** `Endpoint.load()` gives the `local` profile

#### Scenario: A model override
- **WHEN** `CHATINHO_MODEL=small` and the `nvidia` profile sets another model
- **THEN** the loaded endpoint has model `small` and the profile's URL and key

#### Scenario: An unknown profile
- **WHEN** `Endpoint.load("nvdia")` is called and the file has `nvidia` and `local`
- **THEN** it fails with an error naming `nvdia` and listing `nvidia` and `local`

#### Scenario: A profile but no file
- **WHEN** `CHATINHO_PROFILE=nvidia` and no profiles file exists
- **THEN** `Endpoint.load()` fails with an error naming `nvidia` and the places searched

#### Scenario: No profiles file
- **WHEN** no profiles file exists, and `OPENAI_API_KEY` and `OPENAI_BASE_URL` are set
- **THEN** `Endpoint.load()` gives an endpoint with that URL, whose key is read from `OPENAI_API_KEY`

### Requirement: From prefixed environment variables
`Endpoint.from_env(prefix)` SHALL build an endpoint from:
- the key in `<prefix>_API_KEY`, read when needed;
- the URL in `<prefix>_BASE_URL`;
- the model in `<prefix>_MODEL`.

The URL and model MUST be left unset when their variables are unset or empty.

#### Scenario: A custom prefix
- **WHEN** `ORBE_OPENAI_API_KEY`, `ORBE_OPENAI_BASE_URL` and `ORBE_OPENAI_MODEL` are set and `Endpoint.from_env("ORBE_OPENAI")` is called
- **THEN** the endpoint has that URL and model, and its key reads `ORBE_OPENAI_API_KEY`

### Requirement: Checking at startup
`Endpoint.check()` SHALL read the key once and raise the key source's error when it cannot be read, so a program can stop before starting its interface. It MUST NOT contact the endpoint. An endpoint without a key source MUST raise an error saying no key is configured.

#### Scenario: A missing key found early
- **WHEN** `check()` is called on an endpoint whose key reads an unset `OPENAI_API_KEY`
- **THEN** it raises an error naming `OPENAI_API_KEY`, and no request is made
