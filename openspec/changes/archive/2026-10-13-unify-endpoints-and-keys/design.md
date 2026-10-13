# Design

## Context

Today a key reaches chatinho in four places, each typed differently (see proposal.md, Why):

| Place | Accepts today | Read when |
|---|---|---|
| `OpenAIConnector(api_key=, base_url=, model=)` | `str` | once, in the cached `AsyncOpenAI` client |
| `McpConnector(token=)` | `str` | when the FastMCP `Client` is built, in `__init__` and again in `initialize()` |
| `McpConnector(delegate={...})` | `str` or callable | once per question, in `_lending()` |
| `McpFrontend(token=)` | `str` | in `__init__`, by `_OneToken` |

The core imports only the standard library, and the batteries live behind extras resolved lazily in `chatinho/__init__.py`. The minimum Python version is 3.12, so `tomllib` is available. Keys travelling on a message are already `Secret`, and nothing persists them.

## Goals / Non-Goals

**Goals:**
- One accepted type for every key or token argument, normalised in one place.
- Reading a key never blocks the event loop.
- Every failure message names a reference and never a value.
- A profile changes provider and model without code changes.

**Non-Goals:**
- Writing to keychains or files.
- Encrypting files ourselves (`cmd:age -d …` covers it).
- Prompting for keys.
- Validating models against the endpoint.
- Profiles for anything other than OpenAI-compatible endpoints.

## Decisions

### Key sources are objects; reference strings are parsed only on request
`chatinho/keys.py` defines:
- the `KeySource` protocol: `read() -> Secret`, synchronous and allowed to block;
- the sources `Env`, `DotEnv`, `File`, `Keyring`, `Command`, `Literal` and `Chain`;
- `KeyUnavailable(Exception)`, whose message carries only the reference and the reason;
- `key(ref: str) -> KeySource`, the reference parser;
- an internal `to_source(value)`, which normalises `str | Secret | Callable[[], str] | KeySource | None`:
  - a `str` or a `Secret` becomes a `Literal`;
  - a callable is wrapped so its result becomes a `Secret`;
  - `None` stays `None`.

A plain `str` is always a literal, so today's callers do not change and a typo such as `"evn:X"` can never silently become a key. Parsing happens only in `key()`, which profile files use.

The alternative was parsing `"env:X"` in every constructor. It is more convenient, but it is ambiguous with real values and turns typos into keys sent to a provider.

### Reading is synchronous; async callers go through the executor
`read()` is synchronous, because `keyring` and `subprocess` block and `McpFrontend` must resolve its token in `__init__`. Async callers use `await read_async(source)`, which calls `loop.run_in_executor(None, source.read)`. The exception is a `Literal` or `Env` source, which is read inline because it cannot block.

The alternative was an async `get()` in the protocol. That makes `McpFrontend.__init__` and user-written sources awkward.

### Caching follows cost
`Env`, `DotEnv` and `File` re-read on every call: they are cheap, and re-reading lets a rotated key take effect. `Keyring` and `Command` cache their first successful value inside the source, behind a lock, so `pass` asks for its PIN once. A cache is never shared between source instances.

`Chain` tries its sources in order. It catches only `KeyUnavailable`, and when every source fails it raises one `KeyUnavailable` that joins the reasons.

### Safety rules live in the sources
- **`File`:** on POSIX (`os.name == "posix"`), a file whose `st_mode & 0o077` is non-zero is refused, with "chmod 600 <path>". `~` is expanded.
- **`DotEnv`:** not permission-checked, because `.env` files are routinely 0644. It parses `KEY=VALUE` lines itself, with optional `export`, `#` comments and surrounding single or double quotes; there is no `python-dotenv` dependency.
- **`Command`:** runs `argv` with `shell=False`, `timeout=30`, and stdin set to `/dev/null`, so the command never reads the chat's own input. Password managers prompt through their own agent (pinentry for `pass`/GPG, the 1Password app for `op`), not through stdin. A non-zero exit or empty output raises `KeyUnavailable` with the command name and exit code. The command's stdout and stderr are never included in the error, since they may hold a partial secret.
- **`Keyring`:** imports `keyring` inside `read()`. An `ImportError` becomes "install chatinho[keyring]", and a missing entry becomes "no keychain entry service/user".
- **Profiles file:** on POSIX it is refused when group or others can write it (`st_mode & 0o022`), because a profile may hold `cmd:`. Reading by others is allowed, since it holds no secret values.

### `Endpoint` is a frozen dataclass in `chatinho/endpoint.py`
Its fields are `base_url: Optional[str]`, `model: Optional[str]`, `api_key` (declared `repr=False`) and `profile: Optional[str]`. `api_key` accepts any key form, and `__post_init__` normalises it with `to_source`, so `Endpoint(api_key="sk-…")` works and the field always holds a key source; `key` is the typed accessor. Its methods are:
- `load(profile=None)`;
- `from_env(prefix)`;
- `with_model()` and `without_key()`, both through `dataclasses.replace`;
- `check()`, which reads `key` and discards the value.

Rules for `load`:
- **Finding the file:** `CHATINHO_PROFILES`, then `./.chatinho.toml`, then `$XDG_CONFIG_HOME/chatinho/profiles.toml` (falling back to `~/.config`). The first file that exists wins, and files are not merged. Merging would make it unclear which file a field came from.
- **Choosing the profile:** the argument, then `CHATINHO_PROFILE`, then the file's `default`.
- **No profile chosen, or no file:** the endpoint comes from `from_env("OPENAI")`, except that the model is read from `CHATINHO_MODEL`. That keeps today's demo environment working.
- **Overrides:** `CHATINHO_MODEL` and `CHATINHO_BASE_URL` override the chosen profile's fields.
- **Validation:** unknown keys in a profile and a non-string `default` raise `ValueError` naming the file and the profile.

### `OpenAIConnector` takes one Endpoint, resolves late and keeps only Secrets
- **Arguments:** `OpenAIConnector(name, endpoint=None, *, temperature, max_tokens, system, memory, credential)`. The separate `api_key`, `base_url` and `model` arguments are removed: the three always travel together, and two ways to say the same thing invited conflicts about which one wins. Another model on the same endpoint is `endpoint.with_model(...)`. With no endpoint, the connector asks OpenAI with `gpt-4o` and no key of its own (lent keys still work).
- **Hiding the key:** the public `api_key` attribute is removed (the key is never an attribute). A `__repr__` shows name, model and URL only, and the kept `endpoint` hides its key in its own `repr`.
- **Reading the key:** in `answer()`, a lent key behaves as today. Otherwise `await read_async(endpoint.key)`, and a `KeyUnavailable` becomes `Reply("<name>: <reason>", status=ERROR)`.
- **Reusing the client:** the cached own-client is keyed by a SHA-256 digest of the key, so a rotated key builds a new client. The digest, not the key, is kept to compare. The old client is closed at once when idle, else when its last request in flight finishes; requests are counted per client. Through a session a peer answers one message at a time, so this only matters when `answer()` is called directly.
- **Updated tests:** every `OpenAIConnector(name, api_key=...)` in the tests becomes `OpenAIConnector(name, Endpoint(api_key=...))`.

The alternative was keeping the separate arguments beside `endpoint=`, with explicit ones winning. It was dropped in review, since it kept two spellings of the same configuration.

### MCP arguments take the same type
- **`McpFrontend(token=)`:** calls `to_source(token).read()` in `__init__` and gives the string to `_OneToken`. `None` or empty raises `ValueError`, as today, and a `KeyUnavailable` propagates.
- **`McpConnector(token=)`:** keeps the source and reads it in `_make_client()`, which runs at construction and in `initialize()`. A missing token therefore fails when the connector is built, matching today's `ValueError`.
- **`McpConnector(delegate={...})`:** each value is normalised with `to_source`. `_lending()` becomes `async`, reads each declared source with `read_async`, and `_ask_remote` awaits it before `call_tool`. A `KeyUnavailable` there returns `Reply("<name>: <reason>", ERROR)` without calling the tool.
- **`build_mcp_session(token=)`:** its type widens to match.

### Exports and extras
`Endpoint`, `KeySource`, `KeyUnavailable`, `key`, `Env`, `DotEnv`, `File`, `Keyring`, `Command`, `Literal` and `Chain` are exported from `chatinho` eagerly; they need only the standard library. `Keyring` imports `keyring` lazily inside `read()`, so it does not go in the lazy-name table. `pyproject.toml` gains `keyring = ["keyring>=24"]`, also added to `all` and `dev`.

### Demos use `Endpoint.load()`
`assistant.py`, `team.py` and `files.py` replace `config()` with:

```python
def endpoint() -> Endpoint:
    found = Endpoint.load()
    try:
        found.check()
    except KeyUnavailable as exc:
        raise SystemExit("%s; see examples/README.md" % exc)
    return found
```

Each calls it from `parts()` and passes `endpoint=` to its connectors; `team.py` passes the same endpoint to both. `lab_server.py` uses `Endpoint.load().without_key()`, and `lab_client.py` delegates `{"llm": Endpoint.load().key}` after `check()`. The missing-key test asserts the new message. That message names `OPENAI_API_KEY` when no profiles file exists, which the test guarantees by pointing `CHATINHO_PROFILES` at a missing path and clearing `CHATINHO_PROFILE`.

## Risks / Trade-offs

- **[`cmd:` in a profiles file runs code]** → The file is refused when group or others can write it; `Command` runs without a shell; the README says to treat the file like a shell rc file.
- **[`Command` or `Keyring` caching keeps a key in memory for the process lifetime]** → This is the same exposure as `Env`, and it is held as a `Secret`. A caller who needs rotation can use a fresh source or a function.
- **[Removing `api_key`, `base_url` and `model` from `OpenAIConnector` breaks existing callers]** → The fix is mechanical (`Endpoint(...)` around the same values), the README shows it, and every caller in the repository is updated. The `api_key` attribute is gone for the same "never an attribute" rule. The release notes in the README call it out.
- **[`.env` is not permission-checked]** → It is documented, and `File` is recommended for a dedicated key.
- **[Keyring on headless Linux or Termux picks a weak or failing backend]** → `KeyUnavailable` carries keyring's reason, and `Chain(...)` lets a profile fall through to `env:` or `file:`.
- **[`DotEnv`'s own parser differs from `python-dotenv` on edge cases]** → It supports the common subset; variable expansion and multi-line values are documented as unsupported.

## Migration Plan

This is one PR, and nothing changes for callers that pass strings. Rolling back means reverting the PR. Profiles files are opt-in.
