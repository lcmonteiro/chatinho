# Design: let-agents-see-attachments

## Context

A message links its files by name and the backend keeps them (REQ-CORE-023);
`locate` answers where one can be opened. `McpFrontend` already reads a reply's
files back that way. `AgentPeer` builds the model's messages in `_history`,
inside the graph's synchronous `extract` node, and caches the compiled graph per
shape of the chat.

## Decisions

### Read before the run, render into the graph's input

`AgentPeer._run` reads the question's files (`read_attached`, async: `locate`
then the read in a thread) before it invokes the graph and passes them rendered
as text in the graph's input (`attached`), which `extract` appends to the
question's `HumanMessage`. `extract` stays synchronous, and the input stays a
string a checkpointer can save. Alternative: an async `_history` that locates —
rejected, it would read the files again on every link-reminder retry.

### Text inline, everything else named

UTF-8 without NUL is text; up to `ATTACHMENT_SHOWN` (20,000) characters are
inlined line by line, a longer line cut on its own, and a note names where
`read_attachment` reads on. Images are named, not sent as image blocks: a model
that takes none fails the whole run.

### `read_attachment` is part of the shape

`Shape` gains a fourth member, whether a question has come with a file; it turns
true once and the graph is rebuilt once with `read_attachment`. An agent that
never sees a file keeps exactly the tools REQ-CONN-016 lists. The tool finds the
question in `configurable[QUESTION_KEY]` of the run's configuration — set on
every run, as the lent key is — and looks in it, then in what `memory`
remembers, newest first.

### The reading moves to a part

`linked_names` and `read_link` move from `frontends/mcp.py` to
`support/parts/attachments.py`, stdlib only, so the agent kit and the frontend
share them; `read_link` also reads a plain path, which `HiveBackend.link` returns.

## Risks

- A remembered file is located on every `read_attachment` call, not cached.
- A file a peer returns through `ask_<peer>` stays unseen (out of scope).
