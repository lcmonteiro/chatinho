# Tasks

## 1. Key sources (`src/chatinho/keys.py`)

- [ ] 1.1 Add the following. Verify with `tests/test_keys.py`: each source yields a `Secret` with whitespace and a trailing newline stripped, `Literal` and a callable normalise through `to_source`, and a plain `str` is never parsed.
  - `KeySource` and `KeyUnavailable`;
  - `Literal`, `Env`, `DotEnv` (its own `KEY=VALUE` parser with `export`, comments and quotes) and `File`;
  - `to_source()` and `read_async()`.
- [ ] 1.2 Add the `File` permission check (POSIX, `st_mode & 0o077`) and the error naming `chmod 600`. Verify with tests for a 0644 file (refused, value absent from the message) and a 0600 file (read); also verify that a rewritten file yields the new key on the next read.
- [ ] 1.3 Add `Command` (no shell, 30 s timeout, cached after the first success, output never in errors) and `Keyring` (lazy import, cached; errors for a missing extra or entry). Verify with tests:
  - a counting script proves `Command` runs once;
  - a failing command's error omits its output;
  - a monkeypatched missing `keyring` module gives the install hint;
  - a fake `keyring` module yields its value.
- [ ] 1.4 Add `Chain` (tries in order, catches only `KeyUnavailable`, joins the reasons) and `key()` (prefixes `env:`, `dotenv:PATH#NAME`, `dotenv:#NAME`, `file:`, `keyring:SERVICE/USER`, `cmd:` via `shlex`, `literal:`). Verify with tests for each prefix, for `evn:X` being refused with the accepted prefixes listed, and for `Chain` naming every failed reference.

## 2. Endpoints and profiles (`src/chatinho/endpoint.py`)

- [ ] 2.1 Add the frozen `Endpoint` with `api_key` set to `repr=False`, plus `with_model()`, `without_key()`, `check()` and `from_env(prefix)`. Verify with `tests/test_endpoint.py`:
  - `repr` hides a literal key;
  - copies differ in one field;
  - `check()` raises a `KeyUnavailable` naming the variable;
  - `from_env("ORBE_OPENAI")` reads the three variables and leaves the URL and model unset when they are empty.
- [ ] 2.2 Add `Endpoint.load()`:
  - the file search order (`CHATINHO_PROFILES`, `./.chatinho.toml`, `$XDG_CONFIG_HOME` or `~/.config`);
  - the profile choice (argument, `CHATINHO_PROFILE`, `default`);
  - the `CHATINHO_MODEL` and `CHATINHO_BASE_URL` overrides;
  - the fallback to the `OPENAI_*` variables;
  - refusing unknown keys, an unknown profile (listing those available) and a group- or world-writable file.

  Verify each scenario of `specs/endpoint-profiles/spec.md` with `tmp_path` files and `monkeypatch`.

## 3. Wiring the sources in

- [ ] 3.1 `OpenAIConnector`:
  - add `endpoint=`, with `model=None` resolving to the argument, then the endpoint, then `gpt-4o`;
  - make `api_key` take any key source, read in `answer()` via `read_async`;
  - turn a `KeyUnavailable` into an error reply;
  - key the own-client by a key digest, so a rotated key rebuilds the client and closes the old one;
  - remove the public `api_key` attribute and add a `__repr__` without the key.

  Verify that the existing `tests/test_openai_connector.py` passes, plus new tests:
  - from an endpoint;
  - an explicit model wins;
  - an unset `Env` key gives an error reply and no request;
  - a rotated file key reaches the stub;
  - `repr()` and `vars()` do not contain `sk-own`.
- [ ] 3.2 MCP:
  - `McpFrontend(token=)` accepts any key source, read in `__init__`;
  - `McpConnector(token=)` is read in `_make_client()`;
  - `delegate` values are normalised, and `_lending()` becomes async and reads per question;
  - a `KeyUnavailable` gives an error reply without calling `ask`;
  - `build_mcp_session(token=)` is widened.

  Verify that the existing MCP tests pass, plus new tests:
  - a frontend with `Env` token lets the right token in;
  - an unset token raises at construction;
  - `delegate={"llm": Env(...)}` lends its value;
  - an unset delegated source gives an error reply, and the remote peer is never asked.
- [ ] 3.3 Export the new names from `chatinho` and add them to `__all__`. Add the `keyring` extra, also to `all` and `dev`. Verify that `tests/test_package_layout.py` and the import-without-extras test still pass, and that `python -c "import chatinho; chatinho.Endpoint, chatinho.Env"` works without `keyring` installed.

## 4. Examples and docs

- [ ] 4.1 Replace `config()` in `assistant.py`, `team.py` and `files.py` with `Endpoint.load()` plus `check()`, where a `KeyUnavailable` exits with a hint. Make `lab_server.py` use `Endpoint.load().without_key()`, and make `lab_client.py` delegate the endpoint's key source. Verify that `tests/test_examples.py` passes with:
  - the missing-key test updated to the new message, with `CHATINHO_PROFILES` pointed at a missing file;
  - a new test that a `CHATINHO_PROFILE` from a `tmp_path` profiles file sets the model and URL the stub receives.
- [ ] 4.2 Document profiles and key sources:
  - `examples/README.md`: a sample `profiles.toml`, the reference prefixes, the precedence, and the `cmd:` and `.env` cautions;
  - the README's keys section;
  - `CLAUDE.md`'s layout (`keys.py`, `endpoint.py`);
  - `docs/SPEC.md`, where credentials are described.

  Verify that every code block in the README section matches the implemented names: grep for each exported name.

## 5. Verification

- [ ] 5.1 Run the CI steps locally:
  - `ruff check src tests examples` must be clean;
  - `mypy src/chatinho` must report no issues;
  - `pytest -q` must pass;
  - `openspec validate --all --strict --no-interactive` must pass.
- [ ] 5.2 Smoke check with real credentials:
  - write a temporary profiles file whose profile reads `env:ORBE_OPENAI_API_KEY` with the working NVIDIA URL and model;
  - run `assistant` and `team` headless through `parts()` with `CHATINHO_PROFILE` set, and check that they answer;
  - check that `Endpoint.from_env("ORBE_OPENAI")` builds the same endpoint.

  Report what was run in the PR, without any key value.
