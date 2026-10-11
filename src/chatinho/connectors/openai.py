"""OpenAI connector for chatinho: any OpenAI-compatible chat endpoint as a peer."""

import logging
from typing import Any, Dict, List, Optional

import openai
from openai import AsyncOpenAI

from ..hooks import HookAnswer, HookContext, HookPeers
from ..hooks import Context, Peers
from ..hooks import connector, name_of, require
from ..message import LOCAL, ChatMessage, Reply, ReplyStatus
from ..query import SELF, Query

logger = logging.getLogger(__name__)

#: What the model remembers by default: what passed between it and anyone,
#: without the replies that failed, the last twenty.
MEMORY = Query(peer=SELF, errors=False).last(20)


@connector("openai")
@require(HookAnswer)
@require(HookContext)
@require(HookPeers)
class OpenAIConnector:
    """Answers with an OpenAI-compatible chat model, remembering the conversation.

    It waits for the model without blocking the chat, sends the model the part
    of the conversation its ``memory`` query selects, and answers with the key
    lent on the message when there is one, else with its own.

    Args:
        name: Its name in the chat.
        api_key: Its own key; optional when every question comes with one lent.
        model: The model to ask.
        temperature: Sampling temperature.
        max_tokens: A cap on the reply's length, or None for the model's own.
        base_url: Any OpenAI-compatible endpoint (Azure, OpenRouter, Ollama, …);
            OpenAI itself when left out.
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
        api_key     : Optional[str] = None,
        *,
        model       : str = "gpt-4o",
        temperature : float = 0.7,
        max_tokens  : Optional[int] = None,
        base_url    : Optional[str] = None,
        system      : Optional[str] = None,
        memory      : Optional[Query] = MEMORY,
        credential  : str = "llm",
    ) -> None:
        self.name        = name
        self.api_key     = api_key
        self.model       = model
        self.temperature = temperature
        self.max_tokens  = max_tokens
        self.base_url    = base_url
        self.system      = system
        self.memory      = memory
        self.credential  = credential
        #: The client for the configured key, built on first use.
        self._client : Optional[AsyncOpenAI] = None

    async def answer(self, msg: ChatMessage) -> Reply:
        """Asks the model, with the conversation so far, and answers with its text."""
        lent = msg.credentials.get(self.credential)
        if lent is None and not self.api_key:
            return Reply("%s: no API key configured or lent as '%s'" % (self.name, self.credential),
                         status=ReplyStatus.ERROR)
        messages = self._messages_for(msg)
        try:
            if lent is not None:
                async with AsyncOpenAI(api_key=lent.reveal(), base_url=self.base_url) as client:
                    return await self._complete(client, messages)
            return await self._complete(self._own_client(), messages)
        except (openai.OpenAIError, OSError) as exc:
            logger.warning("%s: request to %s failed (%s)", self.name, self.model, type(exc).__name__)
            return Reply("%s: could not get an answer (%s)" % (self.name, type(exc).__name__),
                         status=ReplyStatus.ERROR)

    def _own_client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
        return self._client

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
            me     = next((at for at, peer in roster.items() if peer is self), None)
            limit  = self.memory.limit
            # The question is in the conversation too; ask for one more so it
            # does not eat into the limit, then leave it out.
            query  = self.memory if limit is None else self.memory.last(limit + 1)
            earlier = [m for m in self.context(query) if m.id != msg.id]
            if limit is not None:
                earlier = earlier[-limit:] if limit > 0 else []
            for m in earlier:
                messages.append(self._turn(m, me, roster))
        messages.append({"role": "user", "content": msg.text})
        return messages

    @staticmethod
    def _turn(m: ChatMessage, me: Optional[int], roster: Dict[int, Any]) -> Dict[str, str]:
        if m.frm == me:
            return {"role": "assistant", "content": m.text}
        if m.frm == LOCAL:
            return {"role": "user", "content": m.text}
        who = name_of(roster[m.frm]) if m.frm in roster else str(m.frm)
        return {"role": "user", "content": "%s: %s" % (who, m.text)}
