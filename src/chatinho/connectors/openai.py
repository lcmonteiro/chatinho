"""OpenAI connector for chatinho: any OpenAI-compatible chat endpoint as a peer."""

import logging
import time
from typing import Any, Dict, List, Optional

import openai

from ..hooks import HookAnswer, HookContext, HookPeers
from ..hooks import Context, Peers
from ..hooks import connector, require
from ..support.parts.keys.endpoint import Endpoint
from ..support.kits.model import EndpointModel, lent_key
from ..support.parts.keys import KeyUnavailable
from ..support.parts.memory import MEMORY, earlier, speaker
from ..message import ChatMessage, Reply, ReplyStatus
from ..query import Query

logger = logging.getLogger(__name__)


# @req REQ-CONN-001, REQ-CONN-002
@connector("openai")
@require(HookAnswer)
@require(HookContext)
@require(HookPeers)
class OpenAIConnector:
    """
    Answers with an OpenAI-compatible chat model, remembering the conversation.

    It waits for the model without blocking the chat, sends the model the part
    of the conversation its ``memory`` query selects, and answers with the key
    lent on the message when there is one, else with its own.

    Where to ask, which model, and with which key all come from one
    :class:`~chatinho.support.parts.keys.endpoint.Endpoint` — usually a named profile::

        OpenAIConnector("assistant", Endpoint.load())
        OpenAIConnector("local", Endpoint(base_url="http://localhost:11434/v1", model="qwen"))

    It asks through an :class:`~chatinho.support.kits.model.EndpointModel`, the
    model every component calls: its own key is read when a question needs it —
    never at creation — so a rotated key is used without a restart and the key
    is never an attribute.

    Args:
        name: Its name in the chat.
        endpoint: The URL (any OpenAI-compatible one: Azure, OpenRouter, Ollama,
            …; OpenAI itself when unset), the model (``gpt-4o`` when unset) and
            the key. The key is optional when every question comes with one lent.
        temperature: Sampling temperature.
        max_tokens: A cap on the reply's length, or None for the model's own.
        system: The system prompt, sent first with every question.
        memory: Which earlier messages to send, as a :class:`~chatinho.query.Query`
            the session applies; None for none. By default what passed between
            it and anyone, without errors, the last twenty.
        credential: The name of the lent credential to answer with.
    """

    context : Context
    peers   : Peers

    def __init__(
        self,
        name        : str,
        endpoint    : Optional[Endpoint] = None,
        *,
        temperature : float = 0.7,
        max_tokens  : Optional[int] = None,
        system      : Optional[str] = None,
        memory      : Optional[Query] = MEMORY,
        credential  : str = "llm",
    ) -> None:
        #: The model it asks, with its own key or the one lent on a question.
        self._model      = EndpointModel(endpoint)
        self.name        = name
        self.endpoint    = self._model.endpoint
        self.model       = self._model.name
        self.base_url    = self._model.base_url
        self.temperature = temperature
        self.max_tokens  = max_tokens
        self.system      = system
        self.memory      = memory
        self.credential  = credential

    def __repr__(self) -> str:
        return "OpenAIConnector(name=%r, model=%r, base_url=%r)" % (self.name, self.model, self.base_url)

    # @req REQ-CONN-006
    async def shutdown(self) -> None:
        """
        Closes the client its model kept for its own key, so its connections do not outlive the chat.

        By now ``close()`` has finished or cancelled every question, so nothing
        is using it; a lent key's client was already closed with its question.
        """
        await self._model.close()

    # @req REQ-CONN-025
    async def answer(self, msg: ChatMessage) -> Reply:
        """Asks the model, with the conversation so far, and answers with its text."""
        began = time.monotonic()
        reply = await self._asked(msg)
        logger.info("%s asked %s for %s: took %.2fs, %s", self.name, self.model, msg.id,
                    time.monotonic() - began, _outcome(reply))
        return reply

    # @req REQ-CONN-004, REQ-CONN-005
    async def _asked(self, msg: ChatMessage) -> Reply:
        """The model's answer to *msg*, or the error reply that says why there is none."""
        lent = lent_key(msg, self.credential)
        if lent is None and not self._model.has_own_key:
            return Reply("%s: no API key configured or lent as '%s'" % (self.name, self.credential),
                         status=ReplyStatus.ERROR)
        params: Dict[str, Any] = dict(temperature=self.temperature)
        if self.max_tokens is not None:
            params["max_tokens"] = self.max_tokens
        try:
            response = await self._model.complete(self._messages_for(msg), api_key=lent, **params)
        except KeyUnavailable as exc:
            logger.warning("%s: no key (%s)", self.name, exc)
            return Reply("%s: %s" % (self.name, exc), status=ReplyStatus.ERROR)
        except (openai.OpenAIError, OSError) as exc:
            logger.warning("%s: request to %s for %s failed (%s)", self.name, self.model, msg.id,
                           type(exc).__name__)
            return Reply("%s: could not get an answer (%s)" % (self.name, type(exc).__name__),
                         status=ReplyStatus.ERROR)
        return Reply(response.choices[0].message.content or "")

    # @req REQ-CONN-003
    def _messages_for(self, msg: ChatMessage) -> List[Dict[str, str]]:
        """The system prompt, what ``memory`` selects, then the question."""
        messages: List[Dict[str, str]] = []
        if self.system:
            messages.append({"role": "system", "content": self.system})
        if self.memory is not None:
            roster = self.peers()
            me     = getattr(self, "peer_id", None)
            for m in earlier(self.context, self.memory, msg):
                role, content = speaker(m, me, roster)
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": msg.text})
        return messages


def _outcome(reply: Reply) -> str:
    """How a request went, for its log record: the reply's status, never its text."""
    return reply.status.value
