"""
The agent connectors: LangChain agents as chat peers.

Each needs its own extra, so they are imported on first use (PEP 562): asking
for the basic connector must not need deep agents. What they share is
:mod:`chatinho.helpers.agent`.
"""

from typing import Any

#: name -> the module that defines it.
_WHERE = {
    "AgentConnector"     : "chatinho.connectors.agents.basic",
    "DeepAgentConnector" : "chatinho.connectors.agents.deep",
}

__all__ = sorted(_WHERE)


def __getattr__(name: str) -> Any:
    """Imports a connector's module only when the connector is asked for."""
    if name not in _WHERE:
        raise AttributeError("module %r has no attribute %r" % (__name__, name))
    from importlib import import_module
    return getattr(import_module(_WHERE[name]), name)
