# Proposal

## Why

The examples show the machinery but do nothing anyone would keep running. `demo.py` and `headless.py` echo what you type. `agent_inbox.py` prints the answer on the server and returns nothing to the agent that asked. `mcp_server.py` answers with a canned sentence. On top of that, `hooks.py` still says "the eleven hooks" while `docs/SPEC.md` documents fourteen, and only `mcp_server.py` is exercised by CI, so drift goes unnoticed.

Now that `OpenAIConnector` is non-blocking, remembers the conversation through a `Query`, and answers with a lent key, the examples can be real tools: you run them with an OpenAI-compatible key and get something useful back.

## What Changes

- **New demos.** Each reads `OPENAI_API_KEY` (required), `OPENAI_BASE_URL` (optional, for any compatible endpoint) and `CHATINHO_MODEL` (optional) from the environment. When the key is missing, each exits with a one-line hint instead of a traceback.
  - `examples/assistant.py`: a terminal assistant with one LLM peer. Its history is kept in SQLite (`DatabaseBackend`), so closing and reopening continues the conversation.
  - `examples/team.py`: two LLM roles in one chat. `@coder` writes, and `@reviewer` reviews what the coder said, because it remembers the whole room (`memory=Query(errors=False)`).
  - `examples/files.py`: `/read <path> [question]` reads a local text file and asks the LLM about it, so you can ask questions about your own code or notes.
  - `examples/lab_server.py` and `examples/lab_client.py`:
    - `lab_server.py` is a session served over MCP. It has no key of its own and answers with the key the client lends (`llm`).
    - `lab_client.py` is the terminal that asks it and lends its key.
  - `examples/lab_fastmcp_client.py`: the plain FastMCP client, now pointed at the lab.
  - `examples/inbox.py`: lets a script ask the person at the terminal and wait for the answer. `curl -d '{"text":"Deploy to prod?"}' localhost:8765/ask` blocks until you answer in the chat, then prints your answer.
- **`examples/hooks.py`** covers all fourteen hooks, adding `HookKeep`, `HookLink` and `HookLocate`. It stays the runnable half of `docs/SPEC.md`.
- **Removed:**
  - `demo.py`, absorbed by `assistant.py`;
  - `headless.py`, since `hooks.py` is the no-terminal example;
  - `agent_inbox.py`, replaced by `inbox.py`;
  - `mcp_server.py` and `mcp_client.py`, replaced by the lab pair.
- **Docs and scripts:**
  - `run.sh` runs `assistant.py`;
  - `examples/README.md` gets one line per demo (what it solves, how to run it);
  - the README, `CLAUDE.md` and `docs/SPEC.md` point at the new files.
- **CI coverage:** every example is exercised in CI.
  - `hooks.py` runs for real.
  - The LLM demos are built headless against a stubbed `AsyncOpenAI`.
  - The lab pair runs in process with a lent key.
  - `inbox.py` is called over HTTP.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. The examples and their tests change. No library behaviour or spec changes, so the change sets `skip_specs: true`.

## Impact

- **Examples:** `examples/` is rewritten as listed above.
- **Tests:** a new `tests/test_examples.py`. `tests/test_mcp_example.py` is replaced by lab tests in it.
- **Scripts and docs:** `run.sh`, `examples/README.md`, `README.md`, `CLAUDE.md` and `docs/SPEC.md` (references to example files).
- **Library:** no changes to `src/`.
- **Running the demos:** needs `chatinho[all]` (`tui`, `openai`, `sql`, `mcp`) and an OpenAI-compatible key. CI needs no key.
