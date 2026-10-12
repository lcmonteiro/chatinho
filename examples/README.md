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
| `CHATINHO_PROFILE` | the LLM demos and `lab_server` | A profile from your profiles file (below): endpoint, model and where the key is. Without one, the three `OPENAI_*`/`CHATINHO_MODEL` variables below are used. |
| `CHATINHO_PROFILES` | the LLM demos and `lab_server` | Another profiles file; by default `./.chatinho.toml`, else `~/.config/chatinho/profiles.toml`. |
| `OPENAI_API_KEY` | `assistant`, `team`, `files`, `lab_client`, `lab_fastmcp_client` | The key, when no profile is chosen; the demos exit with a hint when it is missing. It is read, never written anywhere. |
| `OPENAI_BASE_URL` | the LLM demos and `lab_server` | Another OpenAI-compatible endpoint, when no profile is chosen: Ollama (`http://localhost:11434/v1`), OpenRouter, Azure, … |
| `CHATINHO_MODEL` | the LLM demos and `lab_server` | The model; overrides the profile's. `gpt-4o-mini` when neither says. |
| `CHATINHO_BASE_URL` | the LLM demos and `lab_server` | Overrides the profile's endpoint. |
| `CHATINHO_DB` | `assistant` | Where the conversation is kept; `assistant.db` by default. Delete it to start fresh. |
| `CHATINHO_MCP_TOKEN` | the lab trio | The bearer token between the lab and its clients. |
| `CHATINHO_LAB_URL` | `lab_client` | Where the lab listens; `http://127.0.0.1:8000/mcp` by default. |
| `CHATINHO_INBOX_TIMEOUT` | `inbox` | Seconds a `POST /ask` waits for your answer; 300 by default. |

## Profiles: endpoint, model and key in one place

Instead of exporting variables, keep each provider as a profile. The key is never in the file, only
where to read it:

```toml
# ~/.config/chatinho/profiles.toml   (or .chatinho.toml in the project; chmod go-w)
default = "nvidia"

[nvidia]
base_url = "https://integrate.api.nvidia.com/v1"
model    = "nvidia/nemotron-3-super-120b-a12b"
api_key  = "env:ORBE_OPENAI_API_KEY"

[openai]
model   = "gpt-4o-mini"
api_key = "keyring:chatinho/openai"      # pip install 'chatinho[keyring]'; keyring set chatinho openai

[local]
base_url = "http://localhost:11434/v1"
model    = "qwen2.5-coder"
api_key  = "literal:ollama"
```

```bash
python examples/assistant.py                         # the default profile
CHATINHO_PROFILE=local python examples/team.py       # same code, Ollama
CHATINHO_MODEL=gpt-4o CHATINHO_PROFILE=openai python examples/assistant.py
```

Where `api_key` can point:

| Reference | Reads | Notes |
|---|---|---|
| `env:NAME` | an environment variable | read anew each time |
| `dotenv:PATH#NAME`, `dotenv:#NAME` | one variable of a dotenv file (`.env` by default) | not permission-checked; keep it out of git |
| `file:PATH` | a whole file | must be `chmod 600`; read anew each time |
| `keyring:SERVICE/USER` | the OS keychain | needs `chatinho[keyring]`; none on Termux |
| `cmd:COMMAND` | what a command prints (`pass show api/openai`, `op read …`, `age -d …`) | run once, without a shell; it runs code, so the file must not be writable by others |
| `literal:VALUE` | the value itself | for endpoints that ignore the key, such as Ollama |

The profile is the one named in code, else `CHATINHO_PROFILE`, else the file's `default`.
`CHATINHO_MODEL` and `CHATINHO_BASE_URL` then override its fields. Errors name the profile, field or
reference, never a key.

## The demos

| File | What it solves | Run it |
|---|---|---|
| `assistant.py` | **Start here.** A terminal assistant on any OpenAI-compatible model. Markdown and code blocks are rendered, and the conversation is kept in SQLite, so the next run picks it up with the model's memory intact. | `python examples/assistant.py` (or `./run.sh`) |
| `team.py` | Two models in one room. `@coder <task>` writes code; `@reviewer <question>` critiques it, because the reviewer's memory is the whole room. | `python examples/team.py` |
| `files.py` | `/read <path> [question]` (quote a path with spaces) sends a local UTF-8 text file (up to 64 KB) and your question to the assistant; keep asking about it afterwards. The file goes to your configured endpoint — only read what you would send there. | `python examples/files.py` |
| `lab_server.py` | A model served over MCP that holds **no key**: each client lends its own with every question, and the lab forgets it after answering. | `CHATINHO_MCP_TOKEN=s3cret python examples/lab_server.py 8000` |
| `lab_client.py` | Your chat, with the lab as a peer, lending your key (your profile's, else `OPENAI_API_KEY`) as the `llm` credential. | `CHATINHO_MCP_TOKEN=s3cret python examples/lab_client.py` |
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
