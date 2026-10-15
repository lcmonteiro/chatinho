# Design

## Context

- **Connectors.** A connector is a plain class declaring hooks. `OpenAIConnector` (`connectors/openai.py`) is the closest model: it builds its history from `context(memory)`, takes an `Endpoint`, and turns failures into `ERROR` replies.
- **Lazy imports.** Each connector sits behind its own extra and is imported lazily: `_WHERE` in `connectors/__init__.py`, `_BEHIND_AN_EXTRA` in `chatinho/__init__.py`.
- **Concurrency.** Since `concurrent-delivery`, `answer` may run for several questions at once. An ask made inside `answer` is nested one level deeper (a `ContextVar` the session sets), and past `max_depth` it gets an `ERROR` reply instead of reaching its peer.
- **LangChain.** In 1.4, `create_agent(model, tools=None, *, system_prompt, middleware, response_format, state_schema, context_schema, checkpointer, store, interrupt_before, interrupt_after, debug, name, cache, ...)` returns a compiled graph. Its tools are fixed when it is compiled. A compiled graph can run concurrently, but not on one checkpointer thread (tested earlier: concurrent runs on the same `thread_id` lose messages).

## Goals / Non-Goals

**Goals:**
- One class a caller configures exactly like `create_agent`.
- The chat's peers and commands as ordinary LangChain tools, with nothing for the caller to wire.
- No change to the session or to any other connector.

**Non-Goals:**
- Lent credentials (`msg.credentials`). The agent uses its own model. A per-question model would mean a per-question graph.
- Attachments produced by the agent, and human-in-the-loop interrupts (`Reply(ASKED)` and resuming). Both are possible later.
- A timeout on tool asks. A slow peer is not an error, and `max_depth` stops loops.
- orbe's own `AgentConnector`. orbe decides separately whether to switch.

## Decisions

### Build lazily, rebuild when the chat changes
The graph is built on the first question, not in `__init__`. The peers and commands are only known once the session grants `peers`/`commands`, and a peer can join later.
- **What gets built:** the connector computes the chat's *shape*: the names that become tools, after the filters. It keeps one compiled graph per shape and rebuilds when the shape changes.
- **Why rebuilding is fine:** compiling takes milliseconds.
- **Locking:** an `asyncio.Lock` makes two concurrent first questions build once.
- *Alternative: generic tools* (`ask_peer(peer, text)`, `list_peers()`) built in `__init__`. Rejected: the model sees names as strings it must first look up, and tool-calling quality is worse than with one named tool per peer.
- *Alternative: pass the session in at call time* (`context=` plus `ToolRuntime`) to a graph the caller built. Rejected by the user: the connector builds the agent.

### Tool names and descriptions
- **Peers.** For a peer, the tool is `ask_<name>`, described as "Ask <name>, another participant in this chat, and get its answer". It has one argument, `question: str`.
- **Commands.** For a command, the tool is `run_<name>`, described by the command's own `description` (or "Run the /<name> command"). It has one argument, `args: str = ""`.
- **Sanitizing.** Names are sanitized to `[A-Za-z0-9_-]` and cut to 64 characters, which is what the OpenAI-compatible APIs accept.
- **Collisions.** A sanitized name that collides with another chat tool gets a numeric suffix. A chat tool that collides with one of the caller's tools is dropped, with a warning: the caller's tool wins.
- **Which peers.** "A peer that answers" is one that declares `HookAnswer`. The connector itself, `LOCAL`, and peers without `HookAnswer` (the backend) are excluded. `ask_user` is the only way to reach `LOCAL`.
- **Building the tools.** They are `StructuredTool.from_function(coroutine=...)` closures over the connector's granted `ask`/`invoke` and the peer's id. They are async, so they run on the loop, inside the task that runs the question. That way they inherit the session's nesting depth: a peer asked through a tool is one level deeper, as the spec requires.
- **Failures.** A tool catches the peer's or command's exception and returns `"<name> failed: <ErrorType>"`. A command that answers nothing returns `"(no answer)"`.

### Memory: the chat's history, without the agent's own tool calls
- **Building the history.** The connector reads `context(memory)` (default `MEMORY` from the OpenAI connector) and drops the question itself. It also drops two kinds of message:
  - every message the connector *sent* that is addressed and is not a reply (its tool asks);
  - every reply to one of those.
- **Turning it into messages.** What remains becomes LangChain messages, following the same rules as `OpenAIConnector._turn`:
  - its own messages become `AIMessage`;
  - the user's become `HumanMessage`;
  - other peers' become `HumanMessage("<name>: text")`.
- **Running.** The question is the last `HumanMessage`, and the run is `ainvoke({"messages": history + [question]})`.
- **Checkpointer.** When `checkpointer` is among the options, the config is `{"configurable": {"thread_id": str(msg.id)}}`. The history is still sent, so a checkpointer only adds the run's own internals.
- *Alternative: a checkpointer thread per chat as the memory.* Rejected: it duplicates the session's history, and concurrent questions corrupt a shared thread.

### The answer
- **Structured.** When `response_format` is set and the result has `structured_response`, the answer is its JSON (`model_dump_json` for pydantic models, `json.dumps` otherwise).
- **Plain.** Otherwise the answer is the last `AIMessage`'s content. A string is used as is; for a list of blocks, the `text` blocks are joined.
- **Failures.** Any exception becomes `Reply("<name>: could not answer (<Type>)", ERROR)`, and is logged without its message, which may echo a prompt. `KeyUnavailable` is the exception: its message names the key reference (never a value), so it is shown.

### Options checked at creation
- `__init__(self, name, model, tools=(), *, memory=MEMORY, peers=None, commands=None, ask_user=False, **agent_options)`.
- `agent_options` is checked against `inspect.signature(create_agent)`, without `model` and `tools`. An unknown key raises `TypeError` there, naming it.
- `name` in the options is the agent's name for LangChain, and defaults to the connector's name. The connector's own name is the first positional argument.

### An Endpoint becomes ChatOpenAI with a key read on demand
`ChatOpenAI(model=endpoint.model or "gpt-4o", base_url=endpoint.base_url, api_key=<async callable>)`. The callable runs `read_async(endpoint.key)` and returns the revealed value; `langchain-openai` 1.x accepts an async callable for `api_key`. An endpoint without a key source becomes a model whose key read raises `KeyUnavailable("... has no API key configured")`, so creating the connector still succeeds.

### Packaging
- **Extra:** `langchain = ["langchain>=1.0", "langchain-openai>=1.0"]`, also added to `all` and `dev`. `uv.lock` is regenerated with `uv lock`.
- **Laziness:** `connectors/agent.py` imports LangChain at module level. Laziness comes from `_WHERE`/`_BEHIND_AN_EXTRA`, as for the other connectors.

## Risks / Trade-offs

- [`langgraph-sdk` moves `websockets` from 17.2 to 16.1.1] → the MCP and HTTP tests run on the new lock. If anything breaks, the extra pins fewer packages (only `langchain-core` + `langgraph`).
- [LangChain runs tools in a way that drops the context variable, so nested depth resets] → a test asks back through a tool and checks the nested question has depth 2, and a loop stops at `max_depth`.
- [Tool-name sanitizing makes two peers' names equal] → a numeric suffix keeps them apart, and a test covers it.
- [The extra is heavy (langgraph and friends)] → it is optional; the core imports none of it, and a test checks that.
- [A model without tool calling] → `create_agent` raises when it binds tools; that becomes an `ERROR` reply on the first question, as any failure does.

## Migration Plan

Additive: a new module, a new extra, and new exports. Nothing existing changes behaviour. Rollback is reverting the change.
