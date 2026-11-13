"""``BasicAgent``: an agent made with LangChain's ``create_agent``."""

import inspect
from typing import Any, Dict, FrozenSet, List

from langchain.agents import create_agent


class BasicAgent:
    """
    Makes the agent with ``create_agent``: a model calling tools in a loop.

    It accepts what ``create_agent`` takes besides the model and the tools, and
    covers no workspace operation, so a peer using its workspace gets every
    ``ws_`` tool.
    """

    name    : str            = "create_agent"
    options : FrozenSet[str] = frozenset(inspect.signature(create_agent).parameters) - {"model", "tools"}
    covered : FrozenSet[str] = frozenset()

    def __repr__(self) -> str:
        return "BasicAgent()"

    async def build(self, model: Any, tools: List[Any], options: Dict[str, Any], peer: Any) -> Any:
        """``create_agent(model, tools=tools, **options)``."""
        del peer
        return create_agent(model, tools=tools, **options)
