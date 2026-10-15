"""What the agent tests share: a scripted chat model that stands in for a real one.

The model answers from a *script*, a function of the messages it is sent, so
each run of the agent is decided by its own conversation and concurrent runs
never take each other's turns. It records what it was sent and which tools it
was given, and calls no network.
"""

import itertools
from typing import Any, Callable, List, Optional, Sequence

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult

Script = Callable[[List[BaseMessage]], AIMessage]

_ids = itertools.count(1)


class FakeModel(BaseChatModel):
    """A chat model whose every answer comes from ``script``."""

    script : Any
    #: The messages of every call, in order.
    sent   : List[List[BaseMessage]] = []
    #: The tool names of every bind_tools, in order.
    tools  : List[List[str]] = []
    #: Raised instead of answering, when set.
    error  : Optional[Any] = None

    @property
    def _llm_type(self) -> str:
        return "fake"

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> "FakeModel":
        self.tools.append([getattr(t, "name", None) or t.get("name") for t in tools])
        return self

    def _answer(self, messages: List[BaseMessage]) -> ChatResult:
        self.sent.append(list(messages))
        if self.error is not None:
            raise self.error
        return ChatResult(generations=[ChatGeneration(message=self.script(list(messages)))])

    def _generate(self, messages: List[BaseMessage], stop: Any = None, run_manager: Any = None,
                  **kwargs: Any) -> ChatResult:
        return self._answer(messages)

    async def _agenerate(self, messages: List[BaseMessage], stop: Any = None, run_manager: Any = None,
                         **kwargs: Any) -> ChatResult:
        return self._answer(messages)


def fake(script: Script) -> FakeModel:
    """A fresh model on *script*, with its own records."""
    return FakeModel(script=script, sent=[], tools=[])


def this_run(messages: List[BaseMessage]) -> List[BaseMessage]:
    """The messages since the question being answered: the last human message on."""
    last = max(i for i, m in enumerate(messages) if isinstance(m, HumanMessage))
    return messages[last:]


def says(text: str) -> Script:
    """A script that answers *text* to everything."""
    return lambda messages: AIMessage(content=text)


def calls(tool: str, then: Callable[[str], str] = lambda result: result, **args: Any) -> Script:
    """A script that calls *tool* with *args* once per question, then answers ``then(result)``."""
    def script(messages: List[BaseMessage]) -> AIMessage:
        results = [m for m in this_run(messages) if isinstance(m, ToolMessage)]
        if not results:
            call = {"name": tool, "args": args, "id": "call-%d" % next(_ids)}
            return AIMessage(content="", tool_calls=[call])
        return AIMessage(content=then(str(results[-1].content)))
    return script


def question(messages: List[BaseMessage]) -> str:
    """The text of the question being answered."""
    return str(this_run(messages)[0].content)
