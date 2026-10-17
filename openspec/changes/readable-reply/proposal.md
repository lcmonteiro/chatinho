# Proposal

## Why

`AgentConnector`'s `ask_<peer>` tools return the peer's `Reply`, and LangChain turns a tool result into the model's text with `str()`. `Reply` is a plain dataclass, so the model reads its repr: `Reply(text='sunny', attachments=(), status=<ReplyStatus.ANSWERED: 'answered'>)`, measured on `main` from the `ToolMessage` LangChain builds. Every answer a peer gives the agent arrives wrapped in Python syntax, and `attachments=()` tells the model nothing, since the `Reply` that `ask` returns never carries attachments. The status is there, but only inside an enum repr. The agent repeats this to the user: `test_a_loop_of_agents_stops_at_max_depth` asserts `"ReplyStatus.ERROR"` in the answer the user receives.

## What Changes

- `str(reply)` reads as what the reply says. A `Reply` that answered is its text alone. A `Reply` that asked back or failed is its status, a colon, and its text, for example `error: quota exceeded`. `repr` is unchanged.
- The `ask_<peer>` tools still return the `Reply` itself. The model now receives that readable form, with the status included where it matters.
- Tests that expected the repr (`str(Reply(...))` compared with an agent's answer, and `"ReplyStatus.ERROR"` in one) expect the readable form instead.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `answer-details`: a new requirement, "A Reply reads as what it says".
- `agent-connector`: in "The chat as tools", the model reads an `ask_` tool's `Reply` in that form.

## Impact

- **Code:** `src/chatinho/message.py`: `Reply` gains `__str__`. `connectors/agent.py` needs no change.
- **Tests:** a test of `str(Reply)` for each status. A test that the model's `ToolMessage` holds the readable form; it fails on `main`. The agent tests that compare with `str(Reply(...))` or look for `ReplyStatus.ERROR` are updated.
- **Docs:** `docs/SPEC.md`, where `Reply` and `ask`'s result are described, and CLAUDE.md, where `ask` returns a `Reply`, each say how it reads.
- **API:** `str()` of a `Reply` changes. Nothing in `src/` or `examples/` calls it today; callers reading `.text` and `.status` are unaffected.
