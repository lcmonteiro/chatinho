"""A router that asks a model which peer a say is for, when the room leaves a choice."""

from typing import Optional

from openai import AsyncOpenAI  # noqa: F401  (replaced by the tests' fake)

from ..hooks import HookContext, HookPeers, HookRoute, Context, Peers, require
from ..message import ChatMessage
from ..query import Query
from ..support.parts.keys.endpoint import Endpoint

#: What the model is told of the conversation by default: the last six
#: messages, without the replies that failed.
ROUTING_MEMORY : Query = Query(errors=False).last(6)

#: The model's word for a say meant for everyone: a broadcast, answered by none.
EVERYONE : str = "everyone"


@require(HookRoute)
@require(HookPeers)
@require(HookContext)
class LLMRouter:
    """
    Routes by ``SimpleRouter``'s rules, and asks a model when they leave a choice.

    A reply to an answering peer goes to that peer, and a say in a room with
    one answering peer to that peer, without a model call. When two or more
    peers could answer, the model is given their names and descriptions, the
    say and the earlier messages *memory* selects, and answers one name or
    ``everyone``. Anything it cannot use is a broadcast, logged, never a
    silenced say.

    Args:
        endpoint: The OpenAI-compatible endpoint, model and key to ask with.
        memory: Which earlier messages the model is told; None for none.
        timeout: The most seconds a say waits on the model.
        credential: The name a key lent on the say goes by; it wins over the
            endpoint's own.

    Raises:
        ValueError: If *timeout* is not a positive number.
    """

    name    : str = "router"
    peers   : Peers
    context : Context

    def __init__(
        self,
        endpoint   : Optional[Endpoint] = None,
        *,
        memory     : Optional[Query] = ROUTING_MEMORY,
        timeout    : float = 10.0,
        credential : str = "llm",
    ) -> None:
        raise NotImplementedError

    async def route(self, msg: ChatMessage) -> Optional[int]:
        """
        The peer that answers *msg*, or None for a broadcast.

        Args:
            msg: A say with ``to`` unset.

        Returns:
            Optional[int]: The id the rules or the model chose; None for
            everyone, or when the model could not choose.
        """
        raise NotImplementedError

    async def shutdown(self) -> None:
        """Closes every client it kept, so no connection outlives the chat."""
        raise NotImplementedError
