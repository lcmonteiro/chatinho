# Tasks

## 1. Test kit

- [x] 1.1 In `tests/fakes/agent.py`, add a tool factory that returns an artifact (`response_format="content_and_artifact"`) with a given name, media type and data, and a script helper that calls it and then answers from a list of texts, one per model call of the run; make `this_run` skip link reminders so a reminder does not start a new run. Verify the existing `tests/test_agent_connector.py` still passes.

## 2. The graph

- [x] 2.1 In `src/chatinho/connectors/agent.py`, add the graph state (`question`, `messages`, `start`, `structured`, `reminders`, `retry`; input `question`, output `text`, `attachments`) and the `extract`, `agent`, `verify` and `load` nodes as described in design.md, compiled per chat shape in place of the bare `create_agent`. Verify with a test that `get_graph()` has exactly the nodes `extract`, `agent`, `verify`, `load` and the edges of the diagram.
- [x] 2.2 Pass the per-question config through the `agent` node to the inner agent. Verify `test_one_thread_per_question` still passes.
- [x] 2.3 Carry the structured response through the state so `load` returns it as JSON. Verify `test_a_structured_answer` still passes.

## 3. Files and links

- [x] 3.1 Collect the run's artifacts in `load` (an `Attachment`, or duck-typed `name`/`media_type`/`data`; text as UTF-8; the last per name) and return them on the `Reply`. Verify with tests for the scenarios "A tool makes a diagram", "A plain answer has no attachments" and "Only this run's files".
- [x] 3.2 Add `link_retries` (default `1`) and the reminder in `verify`. Verify with tests for "A missing link is asked for", "Sent back at most link_retries times", "Verify turned off" and "Linked the first time".

## 4. Says

- [x] 4.1 Declare `HookListen` and `HookSay`; implement `listen` responding to the user's broadcasts with `say(..., reply_to=msg.id, attachments=...)`, sharing one run path with `answer`, and saying the failure text when the run fails. Verify with tests for "The user says something to everyone", "Another peer says something to everyone", "Asked directly" and "The run fails on a say".
- [x] 4.2 In `_history()`, add the parent of each of the connector's own messages whose parent the memory query did not select, just before it. Verify with a test for "It remembers what the user said to everyone", and that "Its tool calls are not memory" still passes.
- [x] 4.3 In `session.py`, carry whether a delivery is put to the peer, and call `answer` only then. Verify with a test in `tests/test_message_delivery.py` for "A peer that listens and answers asks another", and that the agent tests no longer loop.

## 5. Docs and checks

- [x] 5.1 Update the module and class docstrings, the README's Agents section (files, `link_retries`, answering says) and `examples/agent.py` (the lead answers without `@lead`). Verify the example imports and builds its parts without a key error in a test or by running `python -c "import examples.agent"` style check used by the repo.
- [x] 5.2 Run the full test suite and the repo's lint/type checks, and `openspec validate agent-graph --strict`; all pass.
