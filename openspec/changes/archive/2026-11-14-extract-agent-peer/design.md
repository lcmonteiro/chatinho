# Design

## Context

Today `connectors/agent.py` (600 lines) is `AgentConnector`: the `@require` stack, `answer`/`listen`,
the LangGraph wrapper (`extract -> agent -> verify -> load`), the `ask_`/`run_`/`ws_` tools, memory,
and the conversion of results into text and attachments. Only two lines are specific to
`create_agent`: `FACTORY` and `OPTIONS`. `connectors/deep.py` subclasses it, swaps `FACTORY`, `OPTIONS`
and `COVERED`, and overrides `_factory_options()` to build a `CompositeBackend` from the workspace and
prefix the system prompt. Tests reach the internals: `connectors.agent.REMINDER` from
`tests/fakes/agent.py`, `AgentConnector.FACTORY` from `test_built_once`, and `connectors.deep.WHERE`.

The library's rule is "a plain class, no base class". `WorkspaceView` is the one stated exception,
because the behaviour itself is what gets extended. `DeepAgentConnector(AgentConnector)` already
breaks the rule without saying so.

## Goals / Non-Goals

**Goals:**
- The `connectors/` root holds only concrete connectors.
- One place to read what a basic agent is, and one place to read what a deep agent is.
- A third kind of agent can be written as a factory and passed to `AgentPeer`, with no subclassing.
- Behaviour in the chat is identical. The existing tests pass after their imports and names change.

**Non-Goals:**
- No new chat behaviour, tool or option.
- `OpenAIConnector` stays out of this. It is not a LangChain agent and shares only `helpers/memory.py`.
- No deprecation alias for `AgentConnector`.

## Decisions

### 1. The base class receives a factory object, not a function

```
AgentFactory (Protocol)
  name    : str                    used in TypeError messages ("create_agent does not take ...")
  options : FrozenSet[str]         keyword arguments the factory accepts
  covered : FrozenSet[str]         workspace operations its own tools already reach
  async build(model, tools, options, peer) -> runnable
```

A deep agent needs more than `create_deep_agent`. It also needs the set of operations it covers, a
backend that can only be made once the chat is running (it awaits the peer's workspace grants), and
a change to the system prompt. All of that is "how this kind of agent is built", so it goes with the
factory. *Alternative:* a plain callable plus extra constructor arguments (`covered=`, `options=`),
which pushes the deep-specific knowledge back onto every caller. *Alternative:* keep class attributes
and `_factory_options()`, which is the shape being replaced.

`build` is async and receives the peer, so a factory can await grants. That replaces
`_factory_options()`. `options` is passed with `name` defaulted and `checkpointer` removed, because
the outer graph owns the checkpointer, as it does today.

### 2. What AgentPeer exposes to factories

`DeepAgent.build` needs the peer's own workspace, the other peers' read-only views, and "log once
that there is no provider". Today these are private (`_workspaced`, `_said_no_workspace`). `AgentPeer`
gains two documented methods for factories, and the logging-once state moves into the first:

- `async own_workspace() -> Optional[Workspace]`: its own workspace, or `None` when it does not use
  one or the session has no provider. It logs the missing provider once.
- `async others_workspaces() -> Dict[str, WorkspaceView]`: the other peers that already have one,
  asked with `create=False`.

The graph's rebuild key, the chat's "shape", keeps including the names of the other peers that have
a workspace, so `/peers/<name>/` still appears from the next question on.

### 3. Connectors are thin subclasses that pick a factory

```python
@connector("agent")
class BasicAgentConnector(AgentPeer):
    def __init__(self, name, model, tools=(), **options):
        super().__init__(name, model, BasicAgent(), tools, **options)

@connector("deep")
class DeepAgentConnector(AgentPeer):
    def __init__(self, name, model, tools=(), *, workspace=True, agent_memory=None, **options):
        if "backend" in options:
            raise TypeError("DeepAgentConnector takes no backend: its workspace is its backend")
        super().__init__(name, model, DeepAgent(agent_memory), tools, workspace=workspace, **options)
```

The public constructor signatures do not change, apart from the class name. The `@require` stack is
on `AgentPeer`, and subclasses inherit it, as `DeepAgentConnector` already relies on today. The
`backend` refusal stays in the connector, because its message is about the connector. An
`AgentPeer(factory=DeepAgent())` given a backend gets the generic "create_deep_agent does not take
'backend'", which is still correct.

*Alternative considered:* full composition, a single `AgentConnector(factory=...)` with no
subclasses, which keeps the "no base class" rule. It was declined: the user asked for the connectors
to derive from a base, and the two named connectors are what examples and docs teach.

### 4. AgentPeer is the second stated base class

CLAUDE.md is updated to name it next to `WorkspaceView`, with the same reason: what is reused is the
behaviour, and a subclass only chooses a factory and defaults.

### 5. Layout

```
connectors/
  __init__.py          lazy: OpenAIConnector, McpConnector, BasicAgentConnector, DeepAgentConnector
  openai.py, mcp.py
  agents/
    __init__.py        lazy, one extra per connector
    basic.py           BasicAgentConnector
    deep.py            DeepAgentConnector
helpers/agent/         needs chatinho[langchain]
  __init__.py          AgentPeer, AgentFactory, BasicAgent, Interrupted; DeepAgent lazily
  peer.py              AgentPeer: hooks, answer/listen/_run/_failed, graph(), shape, memory
  factory.py           AgentFactory (Protocol) only
  basic.py             BasicAgent (create_agent, OPTIONS from its signature)
  deep.py              DeepAgent (create_deep_agent, CompositeBackend, WHERE, PEERS)  chatinho[deepagents]
  graph.py             AgentInput/Output/State, compile(inner, retries, ...)
  tools.py             tool names, ask_/run_/ws_ builders, Shape
  results.py           text, files, attachment, shown, diffed, REMINDER, DIFF_SHOWN
```

`connectors/agents/` (plural) holds the connectors, and `helpers/agent/` (singular) holds what they
share. This mirrors `connectors/mcp.py` and `helpers/mcp.py`. `helpers/agent/__init__.py` resolves
`DeepAgent` with PEP 562, so `from chatinho.helpers.agent import AgentPeer` never imports
`deepagents`. `chat_model` (Endpoint to ChatOpenAI) moves to `peer.py`, since every factory receives
an already-made model.

### 6. Tests follow the code; one new test for a custom factory

`test_built_once` injects a counting factory instead of patching `FACTORY`. `tests/fakes/agent.py`
imports `REMINDER` from `chatinho.helpers.agent.results`, and the deep tests import `WHERE` from
`chatinho.helpers.agent.deep`. A new `test_agent_peer.py` covers the `agent-peer` spec: a custom
factory, a lazy build, a rebuild on a new peer, an option the factory refuses, `covered` honoured,
and imports.

## Risks / Trade-offs

- [Moving 600 lines hides a behaviour change in a refactor diff] → Move first and rename second, in
  separate commits, and run the full suite after each.
- [`own_workspace`/`others_workspaces` become a semi-public surface on AgentPeer] → Documented as
  "for factories", and covered by `test_agent_peer.py` through a custom factory.
- [`helpers/` was standard-library only] → The `helpers/__init__.py` docstring says `agent/` is behind
  `chatinho[langchain]`, and the architecture test that blocks `deepagents` also imports
  `chatinho.helpers.agent` with `deepagents` blocked.
- [Breaking rename for anyone pinned to a commit] → Not on PyPI and no tags. README examples are
  updated, and `chatinho.AgentConnector` raises a plain `AttributeError`.
- [The "AgentConnector is unchanged" scenario keeps its old title] → OpenSpec cannot rename a
  scenario inside MODIFIED. Its body already says `BasicAgentConnector`, and a task retitles it in
  the main spec after archive.

## Migration Plan

Within the repository, one change:
1. Move the code into `helpers/agent/` and `connectors/agents/`, without renaming yet.
2. Rename `AgentConnector` to `BasicAgentConnector` everywhere.
3. Update the docs.

Rollback is reverting the commits. There is no data, schema or configuration to migrate.
