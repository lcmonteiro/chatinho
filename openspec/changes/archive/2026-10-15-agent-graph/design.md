# Design

## Context

`AgentConnector` (`src/chatinho/connectors/agent.py`) builds one `create_agent` per shape of the chat (its peers and commands), under a lock, and runs it once per question. `_history()` turns the `memory` query into LangChain messages and `_result()` reads the last AI message or the structured response. It declares `HookAnswer` only, so the session never hands it broadcasts (`session.py`, `_deliver`: a broadcast returns before `answer`).

orbe's base agent (`orbe/intelligence/agents/base/`) is the model for this change: a LangGraph graph `extract -> agent -> verify -> load` around an inner `create_agent`, whose `verify` sends the model back once when its answer does not link a file a tool made. See proposal.md for why it moves here; the specs for the observable behavior.

`Attachment.data` is `bytes`; `Say` takes `attachments` but has no `status`.

## Goals / Non-Goals

**Goals:**
- One compiled graph per chat shape, replacing the bare `create_agent`; questions and the user's says both run it.
- The graph's nodes and edges can be inspected (`get_graph()`), as orbe's are.

**Non-Goals:**
- Attachments in the answers of peers asked through `ask_<peer>` tools: those tools still return text.
- A status on says (an error response to a say is plain text).
- Responding to says of other peers, or any change to the session's depth rules. (The session changes only in the delivery fix below.)
- Letting callers add their own nodes to the graph; `middleware=` remains the extension point inside the `agent` node.

## Decisions

### A LangGraph graph around the inner agent

```
START -> extract -> agent -> verify --(retry)--> agent
                               \--(done)--> load -> END
```

The connector compiles a `StateGraph` whose `agent` node invokes the inner `create_agent` (built as today, with the caller's tools, the chat tools and `**agent_options`). The compiled graph replaces the inner agent in `_built`, so it is still built lazily, once per shape, under the same lock.

*Alternative:* an `after_agent` middleware that jumps back to the model. Rejected: it hides the steps the user asked to see as a graph, mixes chatinho's check with the caller's middleware, and keeps its counter in the agent's state, where a checkpointer would persist it across retries.

### State

| Key | Set by | Meaning |
|---|---|---|
| `question` | input | the `ChatMessage` being answered or responded to |
| `messages` | extract, agent, verify | the run's working messages |
| `start` | extract | how many of `messages` came from memory; the run's own messages are `messages[start:]` |
| `structured` | agent | the inner agent's `structured_response`, if any |
| `reminders` | extract, verify | reminders sent in this run |
| `retry` | verify | whether to go back to `agent` |
| `text`, `attachments` | load | the output |

Input schema: `question`; output schema: `text`, `attachments`. `extract` calls `_history(question)` — a closure over the connector, since it needs `context()` and `peers()` — so the hooks stay on the connector and the graph holds no chat state between runs.

### Files come from `ToolMessage.artifact`

`load` scans `messages[start:]` for `ToolMessage`s whose `artifact` is an `Attachment` or has `name`, `media_type` and `data` (duck-typed, so orbe's `Artifact` works unchanged), converts them to `Attachment` (text encoded as UTF-8), and keeps the last one per name, in first-seen order. Tools produce them with LangChain's `response_format="content_and_artifact"`. Restricting the scan to `messages[start:]` is what keeps earlier runs' files out.

### verify

`verify` computes the answer text as `load` would (structured response as JSON, else the last AI message), collects the run's file names, and finds those not present as `](<name>)`. If any are missing and `reminders < link_retries`, it appends a `HumanMessage` naming the missing links as `[<title>](<name>)` and sets `retry`; the conditional edge goes back to `agent`, which re-invokes the inner agent on the extended messages. `link_retries=0` keeps the node but it never retries, so the graph's shape does not depend on the option.

### Checkpointer and config

The `checkpointer` option is taken off the inner agent and given to the outer graph, which gets the per-question config (`thread_id` = the question's id). The `agent` node passes its `config` to the inner agent, which runs as a subgraph and checkpoints under the same thread. A checkpointer on the inner agent alone does not work: invoked from inside a node, it runs as a subgraph of a graph without one and saves nothing.

### Listening

The connector adds `HookListen` and `HookSay`. `listen(msg)` returns at once unless `msg.is_broadcast and msg.is_local`; otherwise it runs the graph and calls `say(text, reply_to=msg.id, attachments=...)`. On failure it says `"<name>: could not answer (<ErrorType>)"`. A message addressed to the connector is not a broadcast, so `listen` ignores it and only `answer` responds. `answer` and `listen` share one `_run(msg) -> (text, attachments)` and differ only in how the result is posted.

### Delivery fix in the session

`_post` already knows which peers a message is put to (its audience) and which only hear it; a reply that resolves an ask has no audience. But `_deliver` decided whether to call `answer` from `msg.to` alone, so a peer that listens got its own resolved replies in `answer` too, and the agent answered its tool results in a loop. `_dispatch`, `_delivery` and `_deliver` now carry an `asked` flag (`at in audience`), and only `asked` deliveries reach `answer` and clear the message's depth.

*Alternative:* the connector returning None for replies to its own asks. Rejected: it leaves the bug for every other peer that listens and answers, the frontend included.

Note that when exactly one peer answers, the session already turns the user's say into a question to it (`_only_answerer`), so such an agent replies rather than says; listening matters once two or more peers answer.

### Memory of answered says

The default memory query (`peer=SELF`) selects messages from, to, or replying to the connector — not a broadcast the connector replied to. `_history()` therefore also looks up, for each of the connector's own messages in the selection whose `reply_to` is not selected, that parent message, from an unfiltered `context()`, and places it just before the response. Parents are added only for the connector's own messages, so memory grows by at most one message per response.

## Risks / Trade-offs

- [Two agents in one chat both respond to every say of the user] → Accepted (like two people in a room); `@name` still addresses one. A flag to mute says can come later.
- [A forgotten link costs one more model call] → Bounded by `link_retries`; `0` turns it off.
- [The extra lookup for parents reads the unfiltered context] → Only when an own message's parent is missing, at most once per history build.
- [A tool returning a very large artifact makes a large attachment] → Same as `Reply` attachments today; the backend decides what it keeps.

## Migration Plan

Additive for callers: the constructor gains `link_retries`; answers that made no files are unchanged. Behavior that changes for existing users: the agent now responds to the user's says. Rollback is reverting the commit. orbe moves to this connector in a separate change once this is merged into `main`.
