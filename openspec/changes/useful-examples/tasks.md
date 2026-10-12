# Tasks

## 1. Test scaffolding

- [x] 1.1 Add `tests/test_examples.py` with the shared pieces:
  - a loader that imports an example file by path (`importlib.util.spec_from_file_location`);
  - the stubbed `AsyncOpenAI` from `test_openai_connector.py`, moved to `tests/llm_kit.py` and shared by both test files;
  - a fixture that sets `OPENAI_API_KEY=test` and patches the stub in.

  Verify that `pytest tests/test_openai_connector.py` still passes.

## 2. LLM demos (each: `parts()` + `main()`, config from the environment)

- [x] 2.1 `examples/assistant.py`: one `OpenAIConnector(name="assistant")`, `DatabaseBackend` at `$CHATINHO_DB` (default `assistant.db`) and `HelpCommand`. Test: a question gets the stub's answer. A second session on the same database recalls the first exchange, and it reaches the model as history.
- [x] 2.2 `examples/team.py`: `coder` with the default memory, and `reviewer` with `memory=Query(errors=False).last(30)`. The welcome message explains `@coder` / `@reviewer`. Test: after the coder answers, asking the reviewer sends the coder's answer to the model as `coder: ...`.
- [x] 2.3 `examples/files.py`: the assistant plus the `/read <path> [question]` command (`HookExecute`, `HookSay`, `HookPeers`; see design.md for why it says rather than asks). It refuses non-files, files over 64 KB and non-UTF-8 files with an error reply. Test:
  - a temp file's content and the question reach the model;
  - each of the three refusals gives an error reply and no model call.
- [x] 2.4 A missing `OPENAI_API_KEY` makes each demo's `main()` exit with the one-line hint, before any UI starts. Test it for `assistant`, `team`, `files` and `lab_client`.

## 3. Lab pair

- [x] 3.1 `examples/lab_server.py` (`build_mcp_session`, an `OpenAIConnector` with no key, declaring the `llm` credential) and `examples/lab_client.py` (`McpConnector` delegating `llm`). Rename `mcp_client.py` to `lab_fastmcp_client.py` and point it at the lab. Test: in process, `McpConnector(server=..., delegate={"llm": "sk-lent"})` gets the stub's answer, and the stub was built with `sk-lent`. Without delegation, the answer is the connector's "no API key" error.
- [x] 3.2 Remove `examples/mcp_server.py` and `tests/test_mcp_example.py`. Move the FastMCP plain-client check there into `test_examples.py`, against the in-process lab.

## 4. Inbox

- [x] 4.1 `examples/inbox.py`: the `http.server` connector from `agent_inbox.py`, with `POST /ask` blocking until the person answers. It returns `200 {"answer": ...}`, or `504` after `$CHATINHO_INBOX_TIMEOUT` (default 300 s). Test:
  - a `Driver` answers "yes" and `urllib` gets `{"answer": "yes"}`;
  - with a 0.2 s timeout and no answer, the response is 504.
- [x] 4.2 Remove `examples/agent_inbox.py`.

## 5. Reference example

- [x] 5.1 `examples/hooks.py`: add `HookKeep` and `HookLink` to `ListArchive`, and `HookLocate` to `Screen`; attach and locate one file during the run; say "fourteen". Test: run it as a subprocess, then check that it exits 0 and that every `Hook*` name in `chatinho.__all__` appears in its output.
- [x] 5.2 Remove `examples/demo.py` and `examples/headless.py`.

## 6. Scripts and docs

- [x] 6.1 Make `run.sh` run `examples/assistant.py`. Rewrite `examples/README.md` with:
  - one row per demo: what it solves and how to run it;
  - the environment variables;
  - "replaced" notes for the removed files.
- [x] 6.2 Update the examples table and the "headless" pointer in `README.md`, the layout and run lines in `CLAUDE.md`, and any example references in `docs/SPEC.md`. Verify that `grep -rn "demo.py\|headless.py\|agent_inbox.py\|mcp_server.py\|mcp_client.py\|eleven" README.md CLAUDE.md docs examples run.sh` finds only the replaced notes.

## 7. Verification

- [x] 7.1 Run the CI steps locally:
  - `ruff check src tests examples` must be clean;
  - `mypy src/chatinho` must report no issues;
  - `pytest -q` must pass;
  - `openspec validate --all --strict --no-interactive` must pass.
- [x] 7.2 Manual smoke check, outside CI: with a real `OPENAI_API_KEY`, run `assistant.py` and `team.py` once each and check that they answer. Report what was run in the PR.
  Run headless through each demo's `parts()` against NVIDIA's OpenAI-compatible endpoint (`nvidia/nemotron-3-super-120b-a12b`): `assistant` answered and recalled the first exchange from a second session on the same database; `team`'s reviewer critiqued the coder's code.
