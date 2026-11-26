"""
``EndpointModel``: the one model every component of chatinho calls (stub).

Needs ``pip install 'chatinho[openai]'``.
"""

from typing import Any, Dict, List, Mapping, Optional

from openai import AsyncOpenAI  # noqa: F401

from ...parts.keys.endpoint import Endpoint
from ....message import ChatMessage, Secret


class EndpointModel:
    """An OpenAI-compatible model on an Endpoint, called with a key per call (stub)."""

    def __init__(self, endpoint: Optional[Endpoint] = None, *,
                 headers: Optional[Mapping[str, str]] = None) -> None:
        endpoint      = endpoint or Endpoint()
        self.endpoint = endpoint
        self.name     = endpoint.model or "gpt-4o"
        self.base_url = endpoint.base_url

    @property
    def has_own_key(self) -> bool:
        return self.endpoint.key is not None

    async def complete(self, messages: List[Dict[str, Any]], *, api_key: Optional[Secret] = None,
                       **params: Any) -> Any:
        raise NotImplementedError

    def chat_model(self) -> Any:
        raise NotImplementedError

    async def close(self) -> None:
        raise NotImplementedError


def lent_key(msg: ChatMessage, credential: str) -> Optional[Secret]:
    """The key *msg* lends under *credential* (stub)."""
    raise NotImplementedError
