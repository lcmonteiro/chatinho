## Why

`AgentConnector` answers with text only and only when asked. An agent whose tools make files (a diagram, a page) cannot hand them to the chat, nothing checks that its answer links the files it made, and what the user says to everyone gets no answer. orbe works around all three with its own connector and its own graph (extract, agent, verify, load). With those steps built into chatinho's connector, orbe — and any other caller — can drop its copy and pass just tools and a prompt.

## What Changes

- `AgentConnector` runs every answer through a built-in graph: **extract** (the chat's memory and the question become the agent's messages), **agent** (the `create_agent` run, as today), **verify** (when the answer leaves out a link to a file the run made, the model is sent back with a reminder) and **load** (the answer's text and the run's files become the result).
- Files made by the agent's tools reach the chat: a tool result whose artifact is an `Attachment` — or anything with `name`, `media_type` and `data` — becomes an attachment of the answer.
- New option `link_retries` (default `1`): how many times the model is sent back for a missing link; `0` turns verify off.
- The connector now also listens: what the **user** says to everyone is responded to with a say replying to it, carrying the same text and attachments an ask would get. Says from other peers are never responded to, so two agents cannot trade says forever. Asks are unchanged, still bounded by the session's `max_depth`.
- Memory includes the user's says the agent responded to, so a conversation held through says is remembered like one held through asks.
- Session fix: a reply that resolves an ask is no longer handed to the asker's `answer` when the asker also listens. The listening agent made the bug visible: it answered its own tool results, in a loop.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `agent-connector`: an answer carries the files the run made, is checked for links to them (`link_retries`), and the user's says are responded to with a say; memory includes those says. The requirement "One question, one run of the agent" is reworded for the graph and for attachments.
- `message-delivery`: a reply that resolves an ask is heard by the asker, never answered again.

## Impact

- `src/chatinho/connectors/agent.py`: the graph (LangGraph `StateGraph`, already a dependency of `langchain`'s `create_agent`), `link_retries`, `listen`, attachment collection, memory of answered says.
- `tests/test_agent_connector.py` and `tests/fakes/agent.py`: tools that return artifacts; new scenarios.
- `examples/agent.py`, README: the lead answers without `@lead`; a tool that makes a file.
- `src/chatinho/session.py`: each delivery knows whether the message is put to that peer; `tests/test_message_delivery.py` gains a regression test.
- No change to hooks or other connectors. The `langchain` extra is unchanged.
