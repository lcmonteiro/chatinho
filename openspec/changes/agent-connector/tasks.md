# Tasks

## 1. Package and test kit

- [x] 1.1 Add the `langchain` extra (`langchain>=1.0`, `langchain-openai>=1.0`) to `pyproject.toml`, also in `all` and `dev`; regenerate `uv.lock` with `uv lock` and install it into `.venv`. Verify: `python -c "import langchain.agents, langchain_openai"` works, and `pytest -q tests/test_mcp_*.py` still passes with the resolved `websockets`.
- [x] 1.2 Add `tests/agent_kit.py`: a scripted fake chat model (subclass of `BaseChatModel` whose `bind_tools` records the tool names it was given, and whose replies are chosen per question from the messages it receives: a tool call, then a final text), so tests run without network. Verify: used by every test in group 2-5.

## 2. The connector

- [x] 2.1 Create `src/chatinho/connectors/agent.py` with `AgentConnector(name, model, tools=(), *, memory=MEMORY, peers=None, commands=None, ask_user=False, **agent_options)`, declaring `HookAnswer`, `HookAsk`, `HookContext`, `HookPeers`, `HookCommands` and `HookInvoke`. Check `agent_options` against `create_agent`'s signature, with `name` defaulting to the connector's name. Verify: tests "options reach create_agent" (the system prompt reaches the fake model) and "an unknown option" (`temprature` raises `TypeError` naming it); creating it calls no model.
- [x] 2.2 Answer one question with one `ainvoke`. The text of the last `AIMessage` is the answer, with text blocks joined; `structured_response` becomes JSON; any exception becomes an `ERROR` reply naming the connector and the type (`KeyUnavailable` shows its message). Verify: tests "the last message is the answer", "a structured answer", "the model fails", and two questions at once both answered.

## 3. The chat as tools

- [x] 3.1 Build the chat tools from `peers()`/`commands()`. `ask_<name>` goes to each other peer declaring `HookAnswer` (not itself, not `LOCAL`), and `run_<name>` to each command with its description. Add `ask_user` when asked for; apply the `peers=`/`commands=` filters; sanitize names to `[A-Za-z0-9_-]{1,64}`, with numeric suffixes on collision; the caller's tools win, with a warning. Tool failures come back as text. Verify: tests "asking another peer", "running a command", "never itself, never the user by default", "limited to the listed peers", "a failing peer", a name with spaces, and two names that sanitize alike.
- [x] 3.2 Build the graph lazily under an `asyncio.Lock`, cached by the chat's shape, and rebuild when the shape changes. Verify: tests "a peer joins later" and "two first questions at once build once" (count `create_agent` calls).
- [x] 3.3 Check recursion through tools: the agent asks `coder` and `coder` asks the agent back; then two agents that always ask each other stop at `max_depth`. Verify: tests "asked back" and a loop that ends with the "too many nested asks" text reaching the agent as a tool result, with the user still answered.

## 4. Memory and model

- [x] 4.1 Build the history from `context(memory)`. Drop the question, the connector's own addressed non-reply messages and the replies to them; map the rest to `AIMessage`/`HumanMessage`, prefixing other peers' names. With a `checkpointer`, pass `thread_id = str(msg.id)`. Verify: tests "it remembers the conversation", "its tool calls are not memory" and "one thread per question" (a recording checkpointer, or an `InMemorySaver` with two distinct thread ids).
- [x] 4.2 Accept an `Endpoint` as `model`: a `ChatOpenAI` for its URL and model (`gpt-4o` by default), with an async `api_key` callable that reads the key source on demand. Verify: tests "created without the key" (an `ERROR` reply naming the unset variable) and that a set key is read when the model is called, not at creation, and is not an attribute of the connector.

## 5. Exports, example and docs

- [x] 5.1 Export `AgentConnector` lazily from `chatinho.connectors` (`_WHERE`) and `chatinho` (`_BEHIND_AN_EXTRA`, `TYPE_CHECKING`, `__all__`, the module docstring's table of extras). Verify: tests "without the extra" (`ImportError` naming `chatinho[langchain]`, with `langchain` hidden from `sys.modules`) and "the core stays light" (`import chatinho` in a subprocess loads no `langchain*` module).
- [x] 5.2 Add `examples/agent.py`: a `lead` agent (`AgentConnector` on the profile's `Endpoint`) that can ask a `coder` (`OpenAIConnector`), plus `/help`, exposing `parts()` like the other demos. Add a headless test in `tests/test_examples.py` with the fake model, checking that `lead` asks `coder` and answers. Verify: `pytest -q tests/test_examples.py`.
- [x] 5.3 Document it: an "Agents" section in `README.md`; the connector and the extra in `CLAUDE.md` (layout and the extras list); `docs/SPEC.md` (connectors); and `examples/README.md` (the new demo). Verify: `grep -n AgentConnector README.md CLAUDE.md docs/SPEC.md examples/README.md` shows each.
- [x] 5.4 Run the CI checks: `ruff check src tests examples`, `mypy src/chatinho`, `pytest -q` and `openspec validate --all --strict --no-interactive`. All pass.
