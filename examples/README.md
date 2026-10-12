# Examples

Small, useful demos, one file each, that you can copy and adapt. Every one is
executed by CI against a stubbed model (`tests/test_examples.py`), so none of them
drifts from the library.

## Setup

```bash
pip install 'chatinho[all]'           # or ./setup.sh from the repo root
export OPENAI_API_KEY=sk-...          # any OpenAI-compatible key
```

| Variable | Used by | Meaning |
|---|---|---|
| `OPENAI_API_KEY` | `assistant`, `team`, `files`, `lab_client`, `lab_fastmcp_client` | The key; the demos exit with a hint when it is missing. It is read from the environment only, never written anywhere. |
| `OPENAI_BASE_URL` | the LLM demos and `lab_server` | Another OpenAI-compatible endpoint: Ollama (`http://localhost:11434/v1`), OpenRouter, Azure, … |
| `CHATINHO_MODEL` | the LLM demos and `lab_server` | The model; `gpt-4o-mini` by default. |
| `CHATINHO_DB` | `assistant` | Where the conversation is kept; `assistant.db` by default. Delete it to start fresh. |
| `CHATINHO_MCP_TOKEN` | the lab trio | The bearer token between the lab and its clients. |
| `CHATINHO_LAB_URL` | `lab_client` | Where the lab listens; `http://127.0.0.1:8000/mcp` by default. |
| `CHATINHO_INBOX_TIMEOUT` | `inbox` | Seconds a `POST /ask` waits for your answer; 300 by default. |

## The demos

| File | What it solves | Run it |
|---|---|---|
| `assistant.py` | **Start here.** A terminal assistant on any OpenAI-compatible model. Markdown and code blocks are rendered, and the conversation is kept in SQLite, so the next run picks it up with the model's memory intact. | `python examples/assistant.py` (or `./run.sh`) |
| `team.py` | Two models in one room. `@coder <task>` writes code; `@reviewer <question>` critiques it, because the reviewer's memory is the whole room. | `python examples/team.py` |
| `files.py` | `/read <path> [question]` (quote a path with spaces) sends a local UTF-8 text file (up to 64 KB) and your question to the assistant; keep asking about it afterwards. The file goes to your configured endpoint — only read what you would send there. | `python examples/files.py` |
| `lab_server.py` | A model served over MCP that holds **no key**: each client lends its own with every question, and the lab forgets it after answering. | `CHATINHO_MCP_TOKEN=s3cret python examples/lab_server.py 8000` |
| `lab_client.py` | Your chat, with the lab as a peer, lending your `OPENAI_API_KEY` as the `llm` credential. | `CHATINHO_MCP_TOKEN=s3cret python examples/lab_client.py` |
| `lab_fastmcp_client.py` | The same question from a plain FastMCP client, without chatinho: the MCP surface is all a client needs. | `CHATINHO_MCP_TOKEN=s3cret python examples/lab_fastmcp_client.py http://127.0.0.1:8000/mcp "what is MCP?"` |
| `inbox.py` | A script asks you a question and waits: `answer=$(curl -s -d '{"text":"Deploy?"}' 127.0.0.1:8765/ask)` returns `{"answer": "..."}` once you reply in the chat, or a 504 after the timeout. No model and no key. | `python examples/inbox.py` |
| `hooks.py` | The fourteen hooks, one peer each, in a chat with no terminal, printing what reaches each door. The runnable half of [`docs/SPEC.md`](../docs/SPEC.md). No key needed. | `python examples/hooks.py` |

Every LLM demo has the same shape: `parts()` returns the connectors, commands and
backend, and `main()` hands them to `build_chat_session` (or `build_mcp_session`).
A test, or your own program, can build the same chat headless from `parts()`.

## Replaced

| Old file | Now |
|---|---|
| `demo.py` | `assistant.py` — a real model instead of an echo, with the same Markdown rendering. |
| `headless.py` | `hooks.py` — a chat with no terminal; `tests/test_examples.py` drives every demo headless. |
| `agent_inbox.py` | `inbox.py` — the HTTP caller now gets the answer back. |
| `mcp_server.py` | `lab_server.py` — a real model answering with the lent key. |
| `mcp_client.py` | `lab_fastmcp_client.py`. |
