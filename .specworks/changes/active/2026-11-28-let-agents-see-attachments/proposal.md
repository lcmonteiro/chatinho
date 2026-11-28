# Proposal: let-agents-see-attachments

## Why

An agent cannot see the files its question came with. `AgentPeer._history`
sends the model `msg.text` alone; the attachments went to the backend
(REQ-CORE-023) and nothing in the agent reads them back, so a question such as
"how many rows has [the data](data.csv)?" reaches the model as a link to
nothing. This is the second gap of the agent architecture review.

## What Changes

- `AgentPeer` declares `HookLocate`. Before each run it reads back every file the
  question's text links (relative link targets, as `McpFrontend` already finds a
  reply's), through `locate` and the link the backend answers.
- A file that is UTF-8 text is put in the question the model is sent, in an
  `<attachment name type>` element, whole or up to 20,000 characters and then cut
  with a note naming `read_attachment` and the line to read on from.
- A file that is not text is named with its type and size, and its content is not sent.
- From the first question that came with a file it could read, the agent has a
  `read_attachment(name, start=1, count=400)` tool: a line window of a file the
  question, or a message its `memory` remembers, links.
- What reads a link back moves to a new part, `support/parts/attachments.py`
  (`linked_names`, `read_link`), shared by `McpFrontend` and the agent; it reads a
  plain local path as well as a `file://` link, which is what `HiveBackend`
  answers with and `McpFrontend` used to miss.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `agents`: adds REQ-AGENT-014, an agent sees the files its question came with.

## Related requirements

- REQ-CORE-023 left: attachments still go to the backend and the message stays text; this only reads them back.
- REQ-CONN-016 left: an agent with no file gets exactly the tools it did; `read_attachment` comes with the first file.
- REQ-CONN-017 left: memory selects the same messages; only the question's turn grows.
- REQ-FRONT-025 left: `McpFrontend` returns a reply's files as before, now also behind a plain path.

## Impact

- Code: `src/chatinho/support/parts/attachments.py` (new), `src/chatinho/support/kits/agent/attachments.py` (new),
  `peer.py`, `graph.py`, `tools.py` in `support/kits/agent/`, and `frontends/mcp.py` importing the part.
- Tests: `tests/agents/test_agent_attachments.py`.
- No new dependency; the light `chatinho[openai]` install is untouched (the part is stdlib only).

## Out of Scope

- A file a peer returns from `ask_<peer>`: `ask` returns a `Reply` with no message id to locate under.
- Showing an image to the model.
- The shared deep-agent worktree under concurrent questions.
