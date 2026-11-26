"""
``EndpointChatModel``: the chat model an Endpoint becomes, taking its key per call.

Needs ``pip install 'chatinho[langchain]'``.
"""

from typing import Any, Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.outputs import ChatResult
from pydantic import ConfigDict, PrivateAttr

from ...parts.keys import KeyUnavailable, read_async
from ...parts.keys.endpoint import Endpoint
from ....message import Secret


class EndpointChatModel(BaseChatModel):
    """A chat model on an Endpoint that takes ``api_key`` on each call (stub)."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    _own : Any = PrivateAttr()

    def __init__(self, endpoint: Endpoint, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        from langchain_openai import ChatOpenAI
        source = endpoint.key
        where  = "profile %r" % endpoint.profile if endpoint.profile else "the endpoint"

        async def api_key() -> str:
            if source is None:
                raise KeyUnavailable("%s has no API key configured" % where)
            return (await read_async(source)).reveal()

        self._own = ChatOpenAI(model=endpoint.model or "gpt-4o", base_url=endpoint.base_url, api_key=api_key)

    @property
    def _llm_type(self) -> str:
        return "chatinho-endpoint"

    async def ainvoke(self, input: Any, config: Any = None, *, api_key: Optional[Secret] = None,
                      **kwargs: Any) -> Any:
        return await self._own.ainvoke(input, config, **kwargs)

    def bind_tools(self, tools: Any, **kwargs: Any) -> Any:
        return self._own.bind_tools(tools, **kwargs)

    def _generate(self, messages: Any, stop: Any = None, run_manager: Any = None,
                  **kwargs: Any) -> ChatResult:
        return self._own._generate(messages, stop=stop, run_manager=run_manager, **kwargs)
