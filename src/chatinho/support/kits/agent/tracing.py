"""
Traces of an agent's run: its graph's nodes, its model calls and its tool calls.

:class:`RunTracer` is a LangChain callback handler made for one run and passed
in that run's config. Each step is traced when it starts (``running``) and when
it ends (``done`` or ``error``), the end following the start. A step's start
follows the step it ran in when it is the first inside it, and otherwise the
last step that ended inside the same one; a tool call follows the end of the
model call that asked for it, so tools run at once share one trace. A run's
traces form a graph:

    extract ─▶ extract ✓ ─▶ agent ─┬─▶ agent ✓ ─▶ verify ─▶ …
                                   └─▶ model ─▶ model ✓ ─┬─▶ tool ws_ls ─▶ ✓
                                                         └─▶ tool ws_read ─▶ ✓

Runs it does not trace (the inner graph's own nodes, a tool node) are only
remembered with their parent, so a traced step's parent is the nearest traced
run above it.
"""

import logging
from typing import Any, Dict, List, Optional, Sequence
from uuid import UUID

from langchain_core.callbacks import AsyncCallbackHandler

from ....hooks import Trace
from ....message import MessageID, TraceID, TraceState

logger = logging.getLogger(__name__)

#: The nodes of the graph around the agent, traced when the run reaches them.
NODES = ("extract", "agent", "verify", "load")

#: How much of a tool's input or output, or a model's answer, a trace keeps.
SHOWN : int = 300


# @req REQ-AGENT-012
class RunTracer(AsyncCallbackHandler):
    """
    Traces one run of an agent on the message *msg_id*.

    Args:
        trace: The peer's ``trace`` grant.
        msg_id: The message the run answers or responds to.
    """

    def __init__(self, trace: Trace, msg_id: MessageID) -> None:
        self._trace  = trace
        self._msg_id = msg_id
        #: The graph's own run: its nodes are the runs directly below it.
        self._root   : Optional[UUID] = None
        #: Every run seen, by id, with the run it started in.
        self._parent : Dict[UUID, Optional[UUID]] = {}
        #: Traced runs: the trace of their start, and what they are called.
        self._start  : Dict[UUID, TraceID] = {}
        self._label  : Dict[UUID, str] = {}
        #: The end of the last step that ended inside each traced run (None: the run itself).
        self._last   : Dict[Optional[UUID], TraceID] = {}
        #: The end of the last model call inside each traced run: what its tool calls follow.
        self._asked  : Dict[Optional[UUID], TraceID] = {}

    # === Nodes ======================================================================

    async def on_chain_start(self, serialized: Optional[Dict[str, Any]], inputs: Any, *, run_id: UUID,
                             parent_run_id: Optional[UUID] = None, tags: Optional[List[str]] = None,
                             metadata: Optional[Dict[str, Any]] = None, **kwargs: Any) -> None:
        self._parent[run_id] = parent_run_id
        if parent_run_id is None and self._root is None:
            self._root = run_id
            return
        name = kwargs.get("name")
        if parent_run_id == self._root and name in NODES and (metadata or {}).get("langgraph_node") == name:
            await self._started(run_id, name, name)

    async def on_chain_end(self, outputs: Any, *, run_id: UUID, **kwargs: Any) -> None:
        await self._ended(run_id, TraceState.DONE, self._label.get(run_id, ""))

    async def on_chain_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        await self._ended(run_id, TraceState.ERROR, "%s failed: %s" % (self._label.get(run_id, ""),
                                                                       type(error).__name__))

    # === Model calls ================================================================

    async def on_chat_model_start(self, serialized: Optional[Dict[str, Any]], messages: List[List[Any]], *,
                                  run_id: UUID, parent_run_id: Optional[UUID] = None, **kwargs: Any) -> None:
        self._parent[run_id] = parent_run_id
        label = "model %s" % _model_name(serialized, kwargs)
        await self._started(run_id, label, label)

    async def on_llm_start(self, serialized: Optional[Dict[str, Any]], prompts: List[str], *, run_id: UUID,
                           parent_run_id: Optional[UUID] = None, **kwargs: Any) -> None:
        self._parent[run_id] = parent_run_id
        label = "model %s" % _model_name(serialized, kwargs)
        await self._started(run_id, label, label)

    async def on_llm_end(self, response: Any, *, run_id: UUID, **kwargs: Any) -> None:
        label = self._label.get(run_id, "model")
        await self._ended(run_id, TraceState.DONE, "%s → %s" % (label, _said(response)))

    async def on_llm_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        await self._ended(run_id, TraceState.ERROR, "%s failed: %s" % (self._label.get(run_id, "model"),
                                                                       type(error).__name__))

    # === Tool calls =================================================================

    async def on_tool_start(self, serialized: Optional[Dict[str, Any]], input_str: str, *, run_id: UUID,
                            parent_run_id: Optional[UUID] = None, inputs: Optional[Dict[str, Any]] = None,
                            **kwargs: Any) -> None:
        self._parent[run_id] = parent_run_id
        name  = kwargs.get("name") or (serialized or {}).get("name") or "tool"
        label = "tool %s" % name
        shown = inputs if inputs is not None else input_str
        await self._started(run_id, label, "%s %s" % (label, _cut(str(shown))))

    async def on_tool_end(self, output: Any, *, run_id: UUID, **kwargs: Any) -> None:
        content = getattr(output, "content", output)
        await self._ended(run_id, TraceState.DONE, "%s → %s" % (self._label.get(run_id, "tool"),
                                                                _cut(str(content))))

    async def on_tool_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        await self._ended(run_id, TraceState.ERROR, "%s failed: %s" % (self._label.get(run_id, "tool"),
                                                                       type(error).__name__))

    # === Inside =====================================================================

    def _traced_parent(self, run_id: UUID) -> Optional[UUID]:
        """The nearest traced run above *run_id*, or None for the run itself."""
        above = self._parent.get(run_id)
        seen  = set()
        while above is not None and above not in self._start and above not in seen:
            seen.add(above)
            above = self._parent.get(above)
        return above if above in self._start else None

    async def _started(self, run_id: UUID, label: str, text: str) -> None:
        inside = self._traced_parent(run_id)
        if label.startswith("tool ") and inside in self._asked:
            # A tool follows the model call that asked for it, whatever ended since: two tools of one
            # turn share that trace even when the first ends before the second's start is traced.
            prev : Optional[TraceID] = self._asked[inside]
        elif inside in self._last:
            prev = self._last[inside]
        else:
            prev = self._start.get(inside) if inside is not None else None
        self._label[run_id] = label
        made = await self._step(TraceState.RUNNING, text, prev)
        if made is not None:
            self._start[run_id] = made

    async def _ended(self, run_id: UUID, state: TraceState, text: str) -> None:
        start = self._start.pop(run_id, None)
        if start is None:
            return
        made = await self._step(state, text, start)
        if made is not None:
            inside = self._traced_parent(run_id)
            self._last[inside] = made
            if self._label.get(run_id, "").startswith("model "):
                self._asked[inside] = made

    async def _step(self, state: TraceState, text: str, prev: Optional[TraceID]) -> Optional[TraceID]:
        """Traces one step; a trace that fails is logged and the run goes on."""
        try:
            return await self._trace(self._msg_id, state, text, prev=prev)
        except Exception:
            logger.debug("Tracing %s of %s failed", text[:40], self._msg_id, exc_info=True)
            return None


def _model_name(serialized: Optional[Dict[str, Any]], extra: Dict[str, Any]) -> str:
    metadata = extra.get("metadata") or {}
    named    = metadata.get("ls_model_name") or extra.get("name") or (serialized or {}).get("name")
    return str(named or "model")


def _said(response: Any) -> str:
    """What a model answered: the tools it wants, or the start of its text."""
    try:
        message = response.generations[0][0].message
    except (AttributeError, IndexError, TypeError):
        return "answered"
    calls : Sequence[Dict[str, Any]] = getattr(message, "tool_calls", None) or ()
    if calls:
        return "wants " + ", ".join(str(call.get("name")) for call in calls)
    return _cut(str(getattr(message, "content", "")))


def _cut(text: str) -> str:
    return text if len(text) <= SHOWN else text[:SHOWN - 1] + "…"
