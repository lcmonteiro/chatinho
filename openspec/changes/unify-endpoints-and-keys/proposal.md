# Proposal

## Why

chatinho moves keys safely once it has them: it lends them per message, wraps them in `Secret`, and clears them after the reply. Where a key *comes from*, though, is left to every caller, and so is the endpoint and model it belongs to. As a result:
- each demo repeats an environment-reading `config()`;
- `OpenAIConnector` takes its key, URL and model as three separate arguments, and the key only as a fixed string, unlike `McpConnector(delegate=...)`, which accepts a function;
- the connector's own key sits in a plain attribute;
- the usual places people keep keys (environment, `.env`, a 0600 file, the OS keychain, a password manager) need glue code each time.

The endpoint and model fail together with the key. While smoke-testing the examples, a valid key on the wrong provider was refused, and then a model id did not exist on the right one. Managing the three as one named profile makes those mistakes visible in one place.

## What Changes

- **New `chatinho.keys` module.** It defines key sources: where a secret lives, read when it is needed and always returned as a `Secret`.
  - `Env`, `DotEnv`, `File`, `Keyring`, `Command` and `Literal`, combined with `Chain`, which tries each source in turn.
  - A parser, `key("env:NAME")`, turns reference strings into sources. It is used by profile files.
  - Errors name the reference, never the value.
  - `Keyring` lives behind a new optional extra, `chatinho[keyring]`.
- **New `Endpoint`.** It bundles `base_url`, `model` and an `api_key` source.
  - `Endpoint.load(profile)` reads a named profile from a TOML profiles file, for example `~/.config/chatinho/profiles.toml`.
  - The profile is chosen by argument, then by `CHATINHO_PROFILE`, then by the file's `default`.
  - `CHATINHO_MODEL` and `CHATINHO_BASE_URL` override single fields.
  - With no profiles file, it falls back to `OPENAI_API_KEY` and `OPENAI_BASE_URL`.
  - `Endpoint.from_env(prefix=...)` reads `<PREFIX>_API_KEY`, `<PREFIX>_BASE_URL` and `<PREFIX>_MODEL`.
  - `with_model()` and `without_key()` derive variants.
  - `check()` resolves the key once, so a program can fail at startup instead of on the first question.
- **`OpenAIConnector`:**
  - It accepts `endpoint=`.
  - It takes an `Endpoint` (`OpenAIConnector(name, endpoint)`) in place of the separate `api_key`, `base_url` and `model` arguments; another model on the same endpoint is `endpoint.with_model(...)`.
  - The key is read when needed and held as a `Secret`.
  - `model` defaults to the endpoint's model, else `gpt-4o`, as today.
  - A key source that cannot produce a key becomes an `error` reply naming the reference.
- **MCP tokens and lending:**
  - `McpConnector(token=..., delegate={...})` and `McpFrontend(token=...)` (and so `build_mcp_session`) accept key sources wherever they accept a string today.
  - A plain string keeps meaning the value itself.
- **Examples:**
  - The LLM demos replace their `config()` with `Endpoint.load()`, so `CHATINHO_PROFILE=local python examples/team.py` works without code changes.
  - `examples/README.md` documents profiles and key sources.
- **Out of scope:**
  - commands that *store* keys (`chatinho keys set`);
  - prompting for a key, which conflicts with the terminal UI owning stdin;
  - OAuth logins;
  - model aliases;
  - switching profiles inside a running chat;
  - checking the model against the endpoint's `/models`.

Elsewhere every existing argument keeps its meaning, and a plain string is still a literal key or token. **BREAKING**: `OpenAIConnector` no longer takes `api_key`, `base_url` or `model`; pass `Endpoint(base_url=..., model=..., api_key=...)` (a plain string key still works there) or `Endpoint.load()`. It no longer exposes its key as the public `api_key` attribute either, since the key is never held in plain text.

## Capabilities

### New Capabilities
- `key-sources`: where keys and tokens are read from, how references are written and resolved, caching, file permission checks, redacted errors, and where key sources are accepted.
- `endpoint-profiles`: the `Endpoint` bundle, the profiles file format and search order, profile selection, environment overrides and fallback, and early checking.

### Modified Capabilities
- `openai-connector`: the endpoint and model come from an `Endpoint` when given. The configured key may be a key source, read when needed and never held in plain text. A source that fails becomes an error reply.
- `credential-delegation`: a delegated value may also be a key source, read once for each question.

## Impact

- **Code:**
  - new `src/chatinho/keys.py` and `src/chatinho/endpoint.py`, both standard library only (`tomllib`, `subprocess`);
  - `connectors/openai.py`, `connectors/mcp.py`, `frontends/mcp.py`, `builder.py`;
  - new exports from `chatinho`.
- **Dependencies:** a new optional extra, `keyring = ["keyring>=24"]`, also added to `all` and `dev`. No new required dependency.
- **Examples:** `assistant.py`, `team.py`, `files.py`, `lab_server.py`, `lab_client.py` and the README.
- **Tests:** new tests for the sources, profiles and connector integration; the example tests are updated for the new missing-key message.
- **Docs:** README, `CLAUDE.md` and `docs/SPEC.md`, where they describe keys and credentials.
