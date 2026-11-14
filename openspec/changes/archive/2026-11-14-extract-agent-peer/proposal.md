# Proposal

## Why

`DeepAgentConnector` gets its agent by subclassing `AgentConnector` and overriding class attributes
(`FACTORY`, `OPTIONS`, `COVERED`) and a hook method (`_factory_options`). The chat around the agent,
which is about 95% of `connectors/agent.py`, therefore lives inside one concrete connector that the
other depends on. The `connectors/` root ends up holding an abstraction, and what makes a deep agent
deep is spread across overrides instead of kept in one place. A third kind of agent would have to
subclass a connector and know which attributes to swap.

## What Changes

- A base class, `AgentPeer(name, model, factory, ...)`, holds everything the two connectors share: the
  `@require` stack, answering and responding, the graph around the agent (extract, agent, verify,
  load), memory, the `ask_`/`run_`/`ws_` tools, attachments and link checks. It **receives** the agent
  factory as an argument instead of reading it from a class attribute.
- `AgentFactory`, a protocol: a `name` for error messages, the `options` it accepts, the workspace
  operations its own tools already `cover`, and `async build(...)`, which makes the agent with the chat
  running. Two implementations:
  - `BasicAgent` builds with LangChain's `create_agent`.
  - `DeepAgent(agent_memory=...)` builds with `create_deep_agent` and owns everything deep-specific:
    the workspace as its backend, `/peers/<name>/`, and the "where your files are" prompt.
- The base class and the factories live under `chatinho/helpers/agent/`. That directory is behind
  `chatinho[langchain]`, and `DeepAgent` is additionally behind `chatinho[deepagents]`.
- The agent connectors move to `chatinho/connectors/agents/`, so the `connectors/` root holds only
  concrete connectors:
  - `connectors/agents/basic.py`: `BasicAgentConnector` = `AgentPeer` + `BasicAgent()`
  - `connectors/agents/deep.py`: `DeepAgentConnector` = `AgentPeer` + `DeepAgent(...)`
- **BREAKING**: `AgentConnector` is renamed `BasicAgentConnector`, with no alias. The modules
  `chatinho.connectors.agent` and `chatinho.connectors.deep` are gone. The package is not on PyPI and
  has no release tags, so a consumer pinned to a commit is unaffected until they move the pin.
- **BREAKING** (internal seam): the class attributes `FACTORY`, `OPTIONS` and `COVERED` and the method
  `_factory_options()` are replaced by the factory object.
- What the connectors do in a chat does not change: same options, tools, memory, replies, backend and
  prompt.

## Capabilities

### New Capabilities
- `agent-peer`: a chat peer around any agent factory, the `AgentFactory` contract (accepted options,
  covered operations, building with the chat running), and where the base class and factories are
  imported from.

### Modified Capabilities
- `agent-connector`: the connector is `BasicAgentConnector`, imported from
  `chatinho.connectors.agents.basic`. `AgentConnector` is no longer exported.
- `deep-agent-connector`: references to `AgentConnector` become `BasicAgentConnector`, and the import
  path becomes `chatinho.connectors.agents.deep`.

## Impact

- **Code**: `src/chatinho/connectors/agent.py` and `deep.py` are split into `helpers/agent/`
  (`peer.py`, `factory.py`, `basic.py`, `deep.py`, `graph.py`, `tools.py`, `results.py`) and
  `connectors/agents/` (`basic.py`, `deep.py`). `connectors/__init__.py`, `chatinho/__init__.py` (the
  lazy table and the `TYPE_CHECKING` imports) and `helpers/__init__.py` are updated.
- **Public API**: `AgentConnector` is replaced by `BasicAgentConnector`. `AgentPeer`, `AgentFactory`,
  `BasicAgent` and `DeepAgent` are importable from `chatinho.helpers.agent`, not from the top-level
  package.
- **Tests**: `test_agent_connector.py`, `test_deep_agent_connector.py`, `test_package_layout.py`,
  `test_architecture.py`, `tests/fakes/agent.py` and `test_examples.py` move to the new names and
  paths. A new test covers a custom factory.
- **Examples and docs**: `examples/agent.py`, `workspaces.py`, `deep_agent.py`, `examples/README.md`,
  `README.md`, `docs/SPEC.md` and `CLAUDE.md`. CLAUDE.md records `AgentPeer` as the library's second
  deliberate base class, after `WorkspaceView`, and describes `connectors/agents/` (plural) and
  `helpers/agent/` (singular) in its layout section.
- **Dependencies**: none new. The extras are unchanged.
