# Design

## Context

`examples/` holds seven files today: `hooks.py`, `demo.py`, `headless.py`, `agent_inbox.py`, `mcp_server.py`, `mcp_client.py` and a README. Two of them, `demo.py` and `headless.py`, define the same `EchoConnector`, and three define their own text frontend. CI runs `ruff` over the folder, and `tests/test_mcp_example.py` starts `mcp_server.py` as a subprocess. Nothing else executes the examples. `run.sh` runs `demo.py`.

What the library now offers that the demos build on:
- `build_chat_session` and `build_mcp_session`;
- `OpenAIConnector`: async, `base_url`, `system`, `memory=Query`, and the lent `llm` key;
- `DatabaseBackend`, which keeps and recalls the conversation;
- `McpConnector(delegate=...)`;
- `@tool` commands, which may declare grants such as `HookAsk` and `HookPeers`.

See proposal.md for the motivation and the list of demos.

## Goals / Non-Goals

**Goals:**
- Each demo does one useful thing with a real model, in one file a reader can copy.
- Every demo is executed by CI without a key or network.
- Running a demo needs an `OPENAI_API_KEY`, and nothing else unless the demo says so.

**Non-Goals:**
- No library changes. If a demo needs one, it is out of this change.
- No shared helper module across demos. Each file stays self-contained, at the cost of a few repeated lines.
- No streaming, tool calling or attachments to the model; the connector does not support them yet.

## Decisions

### Every LLM demo is `parts()` plus `main()`
Each LLM demo defines `parts() -> dict`, which returns the `connectors`, `commands` and `backend` it is made of. `main()` calls `build_chat_session(**parts(), title=..., welcome_message=...)`, or `build_mcp_session` for the lab server.

A test can then import the file, build `ChatSession(frontend=Driver(), **parts())` headless, and drive one exchange against a stubbed `AsyncOpenAI`. This needs no Textual app and no network. Reading the config from the environment happens in `parts()` too, so the test sets `OPENAI_API_KEY=test` with `monkeypatch.setenv`.

The alternative was running each demo as a subprocess. That needs a real terminal for the TUI ones and a real endpoint for the LLM.

### Configuration from the environment, read in one small function per file
The variables are `OPENAI_API_KEY`, `OPENAI_BASE_URL` (passed as `base_url`, `None` when unset) and `CHATINHO_MODEL` (default `gpt-4o-mini`). A missing key raises `SystemExit("set OPENAI_API_KEY (any OpenAI-compatible key); see examples/README.md")` from `main()`, never from import. The function is about six lines, repeated per file, consistent with "copy one file". Keys never appear in code or in the repository.

### `team.py`: two connectors, addressed by name
The roster is `OpenAIConnector(name="coder", system=...)` and `OpenAIConnector(name="reviewer", system=..., memory=Query(errors=False).last(30))`.

With two answering peers, the lone-answerer rule does not apply, so the user writes `@coder ...` or `@reviewer ...` (the terminal's `@name` asks that peer). The reviewer's memory is the whole room, so it sees the coder's answer. The coder's memory is the default (its own exchanges). The welcome message says how to address them.

### `files.py`: a command that asks the LLM
`@tool("read", "Ask the assistant about a local text file")` declares `HookExecute`, `HookAsk` and `HookPeers`. For `/read <path> [question]`, it:
1. resolves `path` relative to the current directory;
2. refuses anything that is not a regular file, or that is larger than 64 KB, or that is not UTF-8, by returning an error `Reply`;
3. finds the `assistant` peer by name in `peers()`;
4. asks it the question, followed by the file in a fenced block, and returns the answer.

The file never leaves the machine except to the configured endpoint. That is the point of the demo, and the README says so.

### Lab pair: the server has no key of its own
- `lab_server.py` uses `build_mcp_session(connectors=[OpenAIConnector(name="lab", system=...)], token=env, port=argv, credentials={"llm": "OpenAI-compatible API key"})`, with no `api_key`.
- `lab_client.py` uses `build_chat_session(connectors=[McpConnector(url=..., token=..., name="lab", delegate={"llm": key})])`.

The lab therefore answers with the client's key, which is what credential delegation is for. The test runs both in process: it uses `McpConnector(server=frontend.server, delegate={"llm": "sk-lent"})` and checks that the stubbed client was built with `sk-lent`. That replaces the subprocess test, which only proved an echo.

### `inbox.py`: the HTTP caller waits for the answer
The connector keeps the `http.server`-on-a-thread shape of `agent_inbox.py`. `POST /ask {"text": ...}` hands the question to the event loop with `run_coroutine_threadsafe(self.ask(LOCAL, text))` and blocks the request thread on `.result(timeout)`. The default timeout is 300 s, from the `CHATINHO_INBOX_TIMEOUT` environment variable. The handler then answers `200 {"answer": ...}`, or `504` on timeout. A script can therefore write `answer=$(curl -s -d '{"text":"Deploy?"}' localhost:8765/ask)`.

It is the only demo without an LLM, so it needs no key. The test drives it with a `Driver` that answers, and calls it with `urllib`.

### `hooks.py` covers all fourteen hooks
`ListArchive` adds `HookKeep` and `HookLink`, holding attachments in a dict. `Screen` adds `HookLocate`. The run attaches one file and locates it, and the header and README say "fourteen". The test runs it as a subprocess and asserts that every `Hook*` name from `chatinho.__all__` appears in its output. A new hook that the example forgets then fails CI.

## Risks / Trade-offs

- **[Repeated config code across demos]** → It is accepted for copyability. It is a handful of lines, and the test checks each demo's missing-key message.
- **[A demo drifts from the connector's API]** → The headless tests build every demo against the real classes, so a signature change fails CI.
- **[`assistant.db` written in the working directory]** → The path comes from `CHATINHO_DB` (default `assistant.db`). The README says where it is and how to start fresh.
- **[`/read` sends a file to a third-party endpoint]** → The welcome text and the README say so, and the command only reads a path the user typed.
- **[Removing `demo.py` loses the "markdown and code blocks" showcase]** → `assistant.py` renders the model's Markdown and code blocks, which is a better showcase.

## Migration Plan

This is one PR. `run.sh` changes target. Anyone running the old files by name finds them listed as replaced in `examples/README.md`.
