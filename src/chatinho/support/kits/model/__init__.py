"""
The one model every component calls: ``EndpointModel``, and its LangChain face.

Needs ``chatinho[openai]``. ``EndpointChatModel`` also needs ``chatinho[langchain]``,
so it is imported on first use (PEP 562), as ``EndpointModel.chat_model()`` does.
"""

from typing import TYPE_CHECKING, Any

from .endpoint import EndpointModel, lent_key

if TYPE_CHECKING:
    from .chat import EndpointChatModel

__all__ = ["EndpointChatModel", "EndpointModel", "lent_key"]


# @req REQ-MODEL-005
def __getattr__(name: str) -> Any:
    """Imports ``EndpointChatModel`` only when it is asked for."""
    if name != "EndpointChatModel":
        raise AttributeError("module %r has no attribute %r" % (__name__, name))
    from .chat import EndpointChatModel
    return EndpointChatModel
