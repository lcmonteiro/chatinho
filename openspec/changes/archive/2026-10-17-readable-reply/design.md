# Design

## Context

- **How a tool's result becomes the model's text.** LangChain's `_format_output` (`langchain_core/tools/base.py`) tries `json.dumps` on a result that is not a string. That raises for a dataclass, so it falls back to `str()`. Measured: a `StructuredTool` returning `Reply("sunny")` produces `ToolMessage` content `"Reply(text='sunny', attachments=(), status=<ReplyStatus.ANSWERED: 'answered'>)"`. With a `__str__` on the returned class, the same call produces whatever `__str__` returns.
- **The tool returns the `Reply` on purpose.** In [lcmonteiro/chatinho#42](https://github.com/lcmonteiro/chatinho/pull/42) the review settled on `_asking` returning the `Reply` itself rather than a string built from it. This design keeps that.
- **Nobody calls `str()` on a `Reply` today.** A search of `src/` and `examples/` finds none. The only callers are tests in `tests/test_agent_connector.py`, which use it to predict what the agent echoes.

## Goals / Non-Goals

**Goals:**

- The model reads a peer's answer as text, and reads the status when the answer is not an answer.
- `_asking` keeps returning the `Reply`.

**Non-Goals:**

- `run_<command>` tools. They return the text `invoke` gives back, which is already plain.
- Changing `repr`, which stays useful for debugging and for test failure messages.
- Showing attachments. The `Reply` that `ask` returns carries none, and `locate` is how they are found.

## Decisions

### 1. `Reply.__str__`, not formatting in the tool

`Reply` gains `__str__`. `_asking` is unchanged.

- **Why:** the tool keeps returning the `Reply`, as decided at review. The readable form is defined once, where the type is, and it holds for any other place that turns a `Reply` into text.
- **Alternative rejected:** `_asking` returns `"%s: %s" % (status, text)`. That reverses the review's decision and leaves `str(Reply)` as a repr everywhere else.

### 2. The text alone when it answered, `<status>: <text>` otherwise

`answered` is what a reply is unless it says otherwise, so labelling it adds noise to every answer the model reads. `asked` and `error` are what the model must not mistake for an answer, so they lead with the status's own value. Values are used rather than new wording so that the text matches `ReplyStatus` and the spec has nothing to keep in step.

## Risks / Trade-offs

- [A `Reply` that answered reads exactly like its text, so `str()` alone can't tell `Reply("error: x")` from `Reply("x", status="error")`] → Code that needs the status reads `.status`. `str()` is for something that reads text, which is the model here.
- [`str()` of a `Reply` changes for any consumer that relied on the repr] → `repr()` gives the old output. The library has no such caller.
