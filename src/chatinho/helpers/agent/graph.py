"""
The graph around an agent: ``extract -> agent -> verify -(retry)-> agent | -(done)-> load``.

``extract`` turns the question into the agent's messages, ``agent`` runs it,
``verify`` sends it back when its answer leaves a file of the run unlinked, and
``load`` turns the run into the answer's text and files.
"""

from typing import Any, Callable, Dict, List, Optional, TypedDict

from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from ...message import Attachment, ChatMessage
from .results import REMINDER, files, text


class AgentInput(TypedDict):
    """What the graph is given: the message to answer or respond to."""

    question : ChatMessage


class AgentOutput(TypedDict):
    """What the graph gives back: the answer and the files the run made."""

    text        : str
    attachments : List[Attachment]


class AgentState(AgentInput, AgentOutput, total=False):
    """
    The whole state; everything but the output stays in the graph.

    Attributes:
        messages: The run's working messages: memory, the question, then the
            model's calls, tool results and any reminder.
        start: How many of ``messages`` came from memory.
        structured: The agent's structured response, when it has one.
        reminders: How many link reminders this run sent.
        retry: Set by ``verify`` when the model must answer again.
    """

    messages   : List[BaseMessage]
    start      : int
    structured : Any
    reminders  : int
    retry      : bool


def _text(state: AgentState) -> str:
    return text(state["messages"][state["start"]:], state.get("structured"))


def _files(state: AgentState) -> List[Attachment]:
    return files(state["messages"][state["start"]:])


def compile_graph(
    inner        : Any,
    history      : Callable[[ChatMessage], List[BaseMessage]],
    retries      : int,
    checkpointer : Any = None,
    name         : Optional[str] = None,
) -> Any:
    """
    The compiled graph around *inner*.

    Args:
        inner: The agent, run as the ``agent`` node.
        history: The agent's messages for a question: memory, then the question.
        retries: How many link reminders one run may send.
        checkpointer: Saves the graph's checkpoints; the agent inside saves under
            the same thread.
        name: The graph's name.

    Returns:
        The compiled graph: ``{"question": msg}`` in, ``{"text", "attachments"}`` out.
    """
    def extract(state: AgentState) -> Dict[str, Any]:
        messages = history(state["question"])
        return {"messages": messages, "start": len(messages) - 1, "reminders": 0, "retry": False}

    async def agent(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
        result = await inner.ainvoke({"messages": state["messages"]}, config=config)
        return {"messages": result["messages"], "structured": result.get("structured_response")}

    def verify(state: AgentState) -> Dict[str, Any]:
        missing = [f.name for f in _files(state) if "](%s)" % f.name not in _text(state)]
        sent    = state.get("reminders", 0)
        if not missing or sent >= retries:
            return {"retry": False}
        links    = ", ".join("[<title>](%s)" % found for found in missing)
        reminder = HumanMessage(content="%s Answer again and include %s." % (REMINDER, links))
        return {"messages": [*state["messages"], reminder], "reminders": sent + 1, "retry": True}

    def load(state: AgentState) -> Dict[str, Any]:
        return {"text": _text(state), "attachments": _files(state)}

    graph = StateGraph(AgentState, input_schema=AgentInput, output_schema=AgentOutput)
    graph.add_node("extract", extract)
    graph.add_node("agent", agent)
    graph.add_node("verify", verify)
    graph.add_node("load", load)
    graph.add_edge(START, "extract")
    graph.add_edge("extract", "agent")
    graph.add_edge("agent", "verify")
    graph.add_conditional_edges("verify", lambda state: "agent" if state.get("retry") else "load",
                                ["agent", "load"])
    graph.add_edge("load", END)
    return graph.compile(checkpointer=checkpointer, name=name)
