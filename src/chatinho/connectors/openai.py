"""OpenAI connector for chatinho: any OpenAI-compatible chat endpoint as a peer."""

import hashlib
import logging
from typing import Any, Dict, List, Optional, Tuple

import openai
from openai import AsyncOpenAI

from ..hooks import HookAnswer, HookContext, HookPeers
from ..hooks import Context, Peers
from ..hooks import connector, require
from ..endpoint import Endpoint
from ..keys import KeyUnavailable, read_async
from ..helpers.memory import MEMORY, earlier, speaker
from ..message import ChatMessage, Reply, ReplyStatus
from ..query import Query

logger = logging.getLogger(__name__)


@connector("openai")
@require(HookAnswer)
@require(HookContext)
@require(HookPeers)
class OpenAIConnector:
    """Answers with an OpenAI-compatible chat model, remembering the conversation.

    It waits for the model without blocking the chat, sends the model the part
    of the conversation its ``memory`` query selects, and answers with the key
    lent on the message when there is one, else with its own.

    Where to ask, which model, and with which key all come from one
    :class:`~chatinho.endpoint.Endpoint` — usually a named profile::

        OpenAIConnector("assistant", Endpoint.load())
        OpenAIConnector("local", Endpoint(base_url="http://localhost:11434/v1", model="qwen"))

    Its own key is read when a question needs it — never at creation — and held
    only as a :class:`~chatinho.message.Secret`, so a rotated key is used
    without a restart and the key is never an attribute.

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
        endpoint         = endpoint or Endpoint()
        self.name        = name
        self.endpoint    = endpoint
        self.model       = endpoint.model or "gpt-4o"
        self.base_url    = endpoint.base_url
        self.temperature = temperature
        self.max_tokens  = max_tokens
        self.system      = system
        self.memory      = memory
        self.credential  = credential
        #: Where its own key is read from, when a question needs it.
        self._key        = endpoint.key
        #: The client for its own key, and a digest of the key it was built with.
        self._client : Optional[Tuple[bytes, AsyncOpenAI]] = None
        #: Requests in flight on each own client, so a rotated-out one is closed only once idle.
        self._using  : Dict[AsyncOpenAI, int] = {}

    def __repr__(self) -> str:
        return "OpenAIConnector(name=%r, model=%r, base_url=%r)" % (self.name, self.model, self.base_url)

    async def shutdown(self) -> None:
        """Closes the client kept for its own key, so its connections do not outlive the chat.

        By now ``close()`` has finished or cancelled every question, so nothing
        is using it; a lent key's client was already closed with its question.
        """
        if self._client is not None:
            client, self._client = self._client[1], None
            await client.close()

    async def answer(self, msg: ChatMessage) -> Reply:
        """Asks the model, with the conversation so far, and answers with its text."""
        lent = msg.credentials.get(self.credential)
        if lent is None and self._key is None:
            return Reply("%s: no API key configured or lent as '%s'" % (self.name, self.credential),
                         status=ReplyStatus.ERROR)
        messages = self._messages_for(msg)
        try:
            if lent is not None:
                async with AsyncOpenAI(api_key=lent.reveal(), base_url=self.base_url) as client:
                    return await self._complete(client, messages)
            return await self._with_own_client(messages)
        except KeyUnavailable as exc:
            logger.warning("%s: no key (%s)", self.name, exc)
            return Reply("%s: %s" % (self.name, exc), status=ReplyStatus.ERROR)
        except (openai.OpenAIError, OSError) as exc:
            logger.warning("%s: request to %s failed (%s)", self.name, self.model, type(exc).__name__)
            return Reply("%s: could not get an answer (%s)" % (self.name, type(exc).__name__),
                         status=ReplyStatus.ERROR)

    async def _with_own_client(self, messages: List[Dict[str, str]]) -> Reply:
        """Asks with its own key's client, closing a rotated-out client once nothing uses it."""
        client = await self._own_client()
        self._using[client] = self._using.get(client, 0) + 1
        try:
            return await self._complete(client, messages)
        finally:
            self._using[client] -= 1
            if not self._using[client]:
                del self._using[client]
                if self._client is None or self._client[1] is not client:
                    await client.close()

    async def _own_client(self) -> AsyncOpenAI:
        """The client for its own key, rebuilt when the key it reads has changed."""
        assert self._key is not None
        key    = (await read_async(self._key)).reveal()
        digest = hashlib.sha256(key.encode()).digest()
        if self._client is not None and self._client[0] == digest:
            return self._client[1]
        if self._client is not None and not self._using.get(self._client[1]):
            await self._client[1].close()          # idle; a busy one closes when it is done
        client       = AsyncOpenAI(api_key=key, base_url=self.base_url)
        self._client = (digest, client)
        return client

    async def _complete(self, client: AsyncOpenAI, messages: List[Dict[str, str]]) -> Reply:
        params: Dict[str, Any] = dict(model=self.model, messages=messages, temperature=self.temperature)
        if self.max_tokens is not None:
            params["max_tokens"] = self.max_tokens
        response = await client.chat.completions.create(**params)
        return Reply(response.choices[0].message.content or "")

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
