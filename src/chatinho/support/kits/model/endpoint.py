"""
``EndpointModel``: the one model every component of chatinho calls.

An OpenAI-compatible endpoint, called with a key per call: the key a message
lends when there is one, else the endpoint's own, read late. It is the only
place in chatinho that builds a client for a model, so every component that
needs one — a connector, a router, an agent — answers a lent key the same way.

Needs ``pip install 'chatinho[openai]'``.
"""

import hashlib
from typing import Any, Dict, List, Mapping, Optional, Tuple

from openai import AsyncOpenAI

from ...parts.keys import KeyUnavailable, read_async
from ...parts.keys.endpoint import Endpoint
from ....message import ChatMessage, Secret


# @req REQ-MODEL-001, REQ-MODEL-002
class EndpointModel:
    """
    An OpenAI-compatible model on an Endpoint, called with a key per call.

    A call given ``api_key`` is made by a client built for it and closed when
    it returns, so a lent key outlives nothing. A call given none uses the
    endpoint's own key, read when the call needs it — never at creation — by
    one client shared between the calls made at once and rebuilt when the key
    it reads changes; the one it replaces is closed once no call is using it.

    Args:
        endpoint: Where to ask, which model, and where its own key is read
            from. The key is optional when every call brings one.
        default: The model asked when the endpoint names none.
        headers: Extra HTTP headers sent with every request, whichever key it
            carries; private, so nothing that shows the model shows them.
    """

    def __init__(
        self,
        endpoint : Optional[Endpoint] = None,
        *,
        default  : str = "gpt-4o",
        headers  : Optional[Mapping[str, str]] = None,
    ) -> None:
        endpoint      = endpoint or Endpoint()
        self.endpoint = endpoint
        self.name     = endpoint.model or default
        self.base_url = endpoint.base_url
        self._headers : Optional[Dict[str, str]] = dict(headers) if headers else None
        #: The client for its own key, and a digest of the key it was built with.
        self._client  : Optional[Tuple[bytes, AsyncOpenAI]] = None
        #: Calls in flight on each own client, so a rotated-out one is closed only once idle.
        self._using   : Dict[AsyncOpenAI, int] = {}

    def __repr__(self) -> str:
        return "EndpointModel(name=%r, base_url=%r)" % (self.name, self.base_url)

    @property
    def has_own_key(self) -> bool:
        """Whether the endpoint names somewhere to read its own key from."""
        return self.endpoint.key is not None

    @property
    def headers(self) -> Optional[Dict[str, str]]:
        """A copy of the headers sent with every request, or None."""
        return dict(self._headers) if self._headers else None

    # @req REQ-MODEL-001
    async def complete(self, messages: List[Dict[str, Any]], *, api_key: Optional[Secret] = None,
                       **params: Any) -> Any:
        """
        One chat completion of *messages*, with *api_key* or the endpoint's own key.

        Args:
            messages: The chat messages, as the OpenAI API takes them.
            api_key: The key for this call alone; None for the endpoint's own.
            **params: Passed to the request as they are (``temperature``, ``max_tokens``, …).

        Returns:
            Any: The SDK's response.

        Raises:
            KeyUnavailable: No key was given and the endpoint has none, or its
                source cannot yield one.
            openai.OpenAIError: The request failed.
        """
        if api_key is not None:
            async with self._openai(api_key.reveal()) as client:
                return await self._create(client, messages, params)
        client = await self._own_client()
        self._using[client] = self._using.get(client, 0) + 1
        try:
            return await self._create(client, messages, params)
        finally:
            self._using[client] -= 1
            if not self._using[client]:
                del self._using[client]
                if self._client is None or self._client[1] is not client:
                    await client.close()

    # @req REQ-MODEL-003, REQ-MODEL-005
    def chat_model(self) -> Any:
        """
        This model as a LangChain chat model that takes ``api_key`` on each call.

        Raises:
            ImportError: LangChain is not installed, naming the extra that brings it.
        """
        try:
            from .chat import EndpointChatModel
        except ImportError as exc:
            raise ImportError("A model as a LangChain chat model needs pip install "
                              "'chatinho[langchain]' (%s)" % exc) from exc
        return EndpointChatModel(self)

    async def own_key(self) -> Secret:
        """
        The endpoint's own key, read now.

        Raises:
            KeyUnavailable: The endpoint has none, or its source cannot yield one.
        """
        source = self.endpoint.key
        if source is None:
            where = "profile %r" % self.endpoint.profile if self.endpoint.profile else "the endpoint"
            raise KeyUnavailable("%s has no API key configured" % where)
        return await read_async(source)

    # @req REQ-MODEL-002
    async def close(self) -> None:
        """Closes the client kept for its own key; one still in use closes when its call returns."""
        if self._client is not None:
            client, self._client = self._client[1], None
            if not self._using.get(client):
                await client.close()

    # === The clients ==================================================================

    async def _own_client(self) -> AsyncOpenAI:
        """The client for its own key, rebuilt when the key it reads has changed."""
        key    = (await self.own_key()).reveal()
        digest = hashlib.sha256(key.encode()).digest()
        if self._client is not None and self._client[0] == digest:
            return self._client[1]
        if self._client is not None and not self._using.get(self._client[1]):
            await self._client[1].close()          # idle; a busy one closes when it is done
        client       = self._openai(key)
        self._client = (digest, client)
        return client

    def _openai(self, key: str) -> AsyncOpenAI:
        return AsyncOpenAI(api_key=key, base_url=self.base_url, default_headers=self._headers)

    async def _create(self, client: AsyncOpenAI, messages: List[Dict[str, Any]],
                      params: Dict[str, Any]) -> Any:
        request: Dict[str, Any] = dict(params, model=self.name, messages=messages)
        return await client.chat.completions.create(**request)


# @req REQ-MODEL-004
def lent_key(msg: ChatMessage, credential: str) -> Optional[Secret]:
    """
    The key *msg* lends under the name *credential*, or None.

    Args:
        msg: The message being answered.
        credential: The name the key is lent under.
    """
    return msg.credentials.get(credential)
