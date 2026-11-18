"""
Traces of an agent's run: its graph's nodes, its model calls and its tool calls.

:class:`RunTracer` is a LangChain callback handler made for one run and passed
in that run's config. Each step is traced when it starts (``running``) and when
it ends (``done`` or ``error``); a step follows the one before it inside the
same parent, so a run's traces form a graph.
"""

from langchain_core.callbacks import AsyncCallbackHandler

from ....hooks import Trace
from ....message import MessageID


class RunTracer(AsyncCallbackHandler):
    """
    Traces one run of an agent on the message *msg_id*.

    Args:
        trace: The peer's ``trace`` grant.
        msg_id: The message the run answers or responds to.
    """

    def __init__(self, trace: Trace, msg_id: MessageID) -> None:
        raise NotImplementedError
