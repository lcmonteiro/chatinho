"""A router that asks a model which peer a say is for, when the room leaves a choice."""

import asyncio
import logging
from typing import Any, Dict, List, Mapping, Optional

import openai

from ..hooks import HookContext, HookPeers, HookRoute, Context, Peers, name_of, require
from ..message import TOOL, ChatMessage
from ..query import Query
from ..support.kits.model import EndpointModel, lent_key
from ..support.parts.keys import KeyUnavailable
from ..support.parts.keys.endpoint import Endpoint
from ..support.parts.memory import earlier
from .simple import answering, simple_route

logger = logging.getLogger(__name__)

#: What the model is told of the conversation by default: the last six
#: messages, without the replies that failed.
ROUTING_MEMORY : Query = Query(errors=False).last(6)

#: The model's word for a say meant for everyone: a broadcast, answered by none.
EVERYONE : str = "everyone"

#: The model asked when the endpoint names none.
DEFAULT_MODEL : str = "gpt-4o-mini"

_INSTRUCTIONS = (
    "You route messages in a group chat. Decide who should answer the last message: one of the "
    "participants below, or %s when it is meant for the whole room or for nobody in particular.\n"
    "Participants:\n%s\n"
    "Answer with exactly one word: a participant's name, or %s."
)

#: What is stripped off the model's answer before it is read as a name.
_QUOTES   = "\"'`"
_TRAILING = ".,!?:;"


# @req REQ-ROUTE-012
def _checked_headers(headers: Optional[Mapping[str, str]]) -> Optional[Dict[str, str]]:
    """
    A copy of *headers*, or None for none; raises ``ValueError`` naming a bad header, never a value.

    Implements REQ-ROUTE-012.
    """
    if headers is None:
        return None
    if not isinstance(headers, Mapping):
        raise ValueError("A router's headers must be a mapping of names to values, got %s"
                         % type(headers).__name__)
    copied : Dict[str, str] = {}
    for name, value in headers.items():
        if not isinstance(name, str) or not isinstance(value, str):
            raise ValueError("A router's header names and values must be strings: %r" % (name,))
        if name.lower() == "authorization":
            raise ValueError("A router's headers cannot set %s: the key authenticates" % name)
        copied[name] = value
    return copied or None


class _Unchosen(Exception):
    """Why the model's choice cannot be used; the say goes to everyone."""


# @req REQ-ROUTE-007, REQ-ROUTE-008, REQ-ROUTE-009, REQ-ROUTE-010, REQ-ROUTE-012
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
        headers: Extra HTTP headers sent with every request to the model, for
            an endpoint that needs them; never ``Authorization``. Implements
            REQ-ROUTE-012.

    Raises:
        ValueError: If *timeout* is not a positive number, or *headers* is
            not a mapping of strings or names ``Authorization``.
    """

    name    : str = "router"
    peers   : Peers
    context : Context

    # @req REQ-ROUTE-009, REQ-ROUTE-012
    def __init__(
        self,
        endpoint   : Optional[Endpoint] = None,
        *,
        memory     : Optional[Query] = ROUTING_MEMORY,
        timeout    : float = 10.0,
        credential : str = "llm",
        headers    : Optional[Mapping[str, str]] = None,
    ) -> None:
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not timeout > 0:
            raise ValueError("A router's timeout must be a positive number of seconds, got %r" % (timeout,))
        #: The model it asks; it holds the headers, so nothing that shows the router shows them.
        self._model     = EndpointModel(endpoint, default=DEFAULT_MODEL, headers=_checked_headers(headers))
        self.endpoint   = self._model.endpoint
        self.model      = self._model.name
        self.base_url   = self._model.base_url
        self.memory     = memory
        self.timeout    = float(timeout)
        self.credential = credential

    def __repr__(self) -> str:
        return "LLMRouter(model=%r, base_url=%r)" % (self.model, self.base_url)

    # @req REQ-ROUTE-007, REQ-ROUTE-009
    async def route(self, msg: ChatMessage) -> Optional[int]:
        """
        The peer that answers *msg*, or None for a broadcast.

        Args:
            msg: A say with ``to`` unset.

        Returns:
            Optional[int]: The id the rules or the model chose; None for
            everyone, or when the model could not choose.
        """
        roster = self.peers()
        chosen = simple_route(msg, roster, self.context)
        if chosen is not None:
            return chosen
        candidates = answering(msg, roster)
        if len(candidates) < 2:
            return None
        try:
            return await asyncio.wait_for(self._choose(msg, roster, candidates), self.timeout)
        except asyncio.TimeoutError:
            logger.warning("Routing %s: the model timed out after %ss; it goes to everyone",
                           msg.id, self.timeout)
        except _Unchosen as exc:
            logger.warning("Routing %s: %s; it goes to everyone", msg.id, exc)
        except KeyUnavailable as exc:
            logger.warning("Routing %s: no key (%s); it goes to everyone", msg.id, exc)
        except (openai.OpenAIError, OSError) as exc:
            logger.warning("Routing %s: the request to %s failed (%s); it goes to everyone",
                           msg.id, self.model, type(exc).__name__)
        return None

    # @req REQ-ROUTE-010
    async def shutdown(self) -> None:
        """Closes the client its model kept, so no connection outlives the chat."""
        await self._model.close()

    # === The choice ===================================================================

    # @req REQ-ROUTE-008, REQ-ROUTE-010, REQ-ROUTE-012
    async def _choose(
        self, msg: ChatMessage, roster: Dict[int, Any], candidates: List[int],
    ) -> Optional[int]:
        """Asks the model and reads its answer; raises ``_Unchosen`` for one it cannot use."""
        messages = self._prompt(msg, roster, candidates)
        lent     = lent_key(msg, self.credential)
        if lent is None and not self._model.has_own_key:
            raise _Unchosen("no API key configured or lent as '%s'" % self.credential)
        response = await self._model.complete(messages, api_key=lent, temperature=0, max_tokens=16)
        return self._read(response.choices[0].message.content or "", roster, candidates)

    # @req REQ-ROUTE-008
    def _prompt(
        self, msg: ChatMessage, roster: Dict[int, Any], candidates: List[int],
    ) -> List[Dict[str, str]]:
        """What the model is told: who may answer, what came before, and the say."""
        listed = []
        for at in candidates:
            description = getattr(roster[at], "description", "")
            text        = description if isinstance(description, str) else ""
            listed.append("- %s: %s" % (name_of(roster[at]), text) if text else "- %s" % name_of(roster[at]))
        system = _INSTRUCTIONS % (EVERYONE, "\n".join(listed), EVERYONE)
        before = earlier(self.context, self.memory, msg)
        lines  = ["%s: %s" % (self._speaker(m, roster), m.text) for m in before]
        lines.append("%s: %s" % (self._speaker(msg, roster), msg.text))
        return [{"role": "system", "content": system},
                {"role": "user", "content": "\n".join(lines)}]

    @staticmethod
    def _speaker(m: ChatMessage, roster: Dict[int, Any]) -> str:
        """Who said *m*, as the model reads it."""
        if m.frm == TOOL:
            return "tool"
        return name_of(roster[m.frm]) if m.frm in roster else str(m.frm)

    # @req REQ-ROUTE-008, REQ-ROUTE-009
    @staticmethod
    def _read(answer: str, roster: Dict[int, Any], candidates: List[int]) -> Optional[int]:
        """The candidate *answer* names, None for everyone; raises ``_Unchosen`` otherwise."""
        word = answer.strip().strip(_QUOTES).strip()
        if word.startswith("@"):
            word = word[1:]
        word = word.rstrip(_TRAILING).strip().strip(_QUOTES).lower()
        if word == EVERYONE:
            return None
        named = [at for at in candidates if name_of(roster[at]).lower() == word]
        if len(named) == 1:
            return named[0]
        if named:
            raise _Unchosen("the model named %r, which %d peers share" % (word[:40], len(named)))
        raise _Unchosen("the model named no peer that answers (%d characters)" % len(answer))
