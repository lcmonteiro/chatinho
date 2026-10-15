# Proposal

## Why

chatinho can put a single model into a chat (`OpenAIConnector`) and another chatinho session (`McpConnector`), but not an *agent*: a model that calls tools in a loop. LangChain's `create_agent` is the common way to build one, and orbe already wraps one by hand (its own `AgentConnector`). That wrapper cannot reach the chat: its agent cannot ask the other peers or run the chat's commands. Now that delivery is concurrent and asks may recurse (`concurrent-delivery`), an agent that asks a peer which asks it back is safe, so the chat can become the agent's toolbox.

## What Changes

- **A new connector, `AgentConnector`**, in `chatinho.connectors.agent`. It builds a LangChain agent with `create_agent` and takes the same parameters (`model`, `tools`, `system_prompt`, `middleware`, `response_format` and the rest), passing them through unchanged. It adds the chat's own tools to `tools`.
- **One question, one run.** Each question it is asked runs the agent once (`ainvoke`). The answer is the text of the agent's last message, or its structured response as JSON when `response_format` is set. A failure becomes an `ERROR` reply.
- **The chat as tools:**
  - one tool per other peer that answers (`ask_<name>`), which asks that peer and returns its answer;
  - one tool per command (named after it, with its description), which runs it.
  - The tools are built on the first question, from who is in the chat then, and rebuilt when the peers or commands change.
  - The agent never gets a tool for itself.
  - An optional `ask_user` tool asks the user (off by default).
  - Optional `peers=` and `commands=` lists limit what it sees.
- **Memory comes from the chat.** Earlier messages come from `context(memory)`, with the same default query as `OpenAIConnector`, so the agent needs no checkpointer. If one is given, every question runs on its own thread (`thread_id` = the question's id), never on one shared by the whole chat.
- **The model may be an `Endpoint`.** It becomes an OpenAI-compatible chat model whose key is read from its key source when needed, never stored.
- **A new extra, `chatinho[langchain]`** (`langchain`, `langchain-openai`). `AgentConnector` is importable from `chatinho` and `chatinho.connectors`, lazily like the other connectors. Without the extra, it says which extra to install.

## Capabilities

### New Capabilities
- `agent-connector`: a LangChain agent as a chat peer. It covers how it is built, how a question is answered, the chat tools it gets and their limits, where its memory comes from, the model it accepts, and the extra it needs.

### Modified Capabilities
None.

## Impact

- **New code:** `src/chatinho/connectors/agent.py` and `tests/test_agent_connector.py` (with a fake chat model, so no network is needed).
- **Wiring:** `src/chatinho/connectors/__init__.py` and `src/chatinho/__init__.py` gain the lazy `AgentConnector` export.
- **Packaging:** `pyproject.toml` gains the `langchain` extra, also added to `all` and `dev`, and `uv.lock` is regenerated. The resolver moves `websockets` from 17.2 to 16.1.1 for `langgraph-sdk`, and the MCP tests must still pass.
- **Docs:** `README.md`, `CLAUDE.md`, `docs/SPEC.md` and `examples/README.md`. A new example, `examples/agent.py`, joins the headless example tests.
- **Builds on `concurrent-delivery`:** recursion bounded by `max_depth`, concurrent questions and the never-block rule. Nothing in the session changes.
- **Out of scope:**
  - lent credentials (the agent uses its own model's key);
  - attachments produced by the agent;
  - human-in-the-loop interrupts;
  - changing orbe's own `AgentConnector`.
