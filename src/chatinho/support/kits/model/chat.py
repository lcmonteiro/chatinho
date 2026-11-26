"""
``EndpointChatModel``: the chat model an Endpoint becomes, taking its key per call.

It is called as any LangChain chat model is, and takes one keyword more::

    model = EndpointChatModel(Endpoint.load())
    await model.ainvoke(messages)                          # the endpoint's own key
    await model.ainvoke(messages, api_key=Secret(key))     # this key, for this call

Inside an agent, LangChain calls the model itself and no caller can add the
keyword, so a call without one takes ``configurable["api_key"]`` from the run's
configuration — where ``AgentPeer`` puts the key lent on the question.

Needs ``pip install 'chatinho[langchain]'``.
"""

from typing import Any, AsyncIterator, Iterator, List, Optional

from langchain_core.callbacks import AsyncCallbackManagerForLLMRun, CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_core.outputs import ChatGenerationChunk, ChatResult
from langchain_core.runnables import RunnableConfig
from langchain_core.runnables.config import ensure_config
from pydantic import ConfigDict, PrivateAttr

from ...parts.keys import KeyUnavailable, read_async
from ...parts.keys.endpoint import Endpoint
from ....message import Secret


# @req REQ-MODEL-003
class EndpointChatModel(BaseChatModel):
    """
    A chat model on an OpenAI-compatible Endpoint that takes ``api_key`` on each call.

    The key of a call is, in order: the ``api_key`` it was given, the
    ``api_key`` its run's configuration carries under ``configurable``, and
    the endpoint's own key, read when the model is called — never at creation,
    and never kept as text. A call with a key is made by a client built for it
    and dropped with it, so no key it was given outlives the call.

    Asynchronous only: ``invoke`` and ``stream`` raise ``NotImplementedError``,
    since the endpoint's key is read by a coroutine.

    Bound tools keep all of this: ``bind_tools`` binds the tools as
    ``ChatOpenAI`` formats them to this model, not to ``ChatOpenAI``. One
    consequence: ``create_agent`` does not see an OpenAI model here, so a
    ``response_format`` is answered through a tool rather than the provider's
    structured output.

    Args:
        endpoint: Where to ask, which model (``gpt-4o`` when it names none),
            and where its own key is read from.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    #: The endpoint's own model, keyed by a function that reads its key source.
    _own      : Any = PrivateAttr()
    _model    : str = PrivateAttr()
    _base_url : Optional[str] = PrivateAttr()

    def __init__(self, endpoint: Endpoint, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        source = endpoint.key
        where  = "profile %r" % endpoint.profile if endpoint.profile else "the endpoint"

        async def own_key() -> str:
            if source is None:
                raise KeyUnavailable("%s has no API key configured" % where)
            return (await read_async(source)).reveal()

        self._model    = endpoint.model or "gpt-4o"
        self._base_url = endpoint.base_url
        self._own      = self._openai(own_key)

    def __repr__(self) -> str:
        return "%s(model=%r, base_url=%r)" % (type(self).__name__, self._model, self._base_url)

    @property
    def _llm_type(self) -> str:
        return "chatinho-endpoint"

    # === Calling it ==================================================================

    async def ainvoke(self, input: Any, config: Optional[RunnableConfig] = None, *,
                      stop: Optional[List[str]] = None, api_key: Optional[Secret] = None,
                      **kwargs: Any) -> AIMessage:
        """Calls the model as ``BaseChatModel.ainvoke`` does, with *api_key* or the run's key."""
        return await super().ainvoke(input, config, stop=stop, api_key=_key_of(api_key, config), **kwargs)

    async def astream(self, input: Any, config: Optional[RunnableConfig] = None, *,
                      stop: Optional[List[str]] = None, api_key: Optional[Secret] = None,
                      **kwargs: Any) -> AsyncIterator[AIMessageChunk]:
        """Streams the model as ``BaseChatModel.astream`` does, with *api_key* or the run's key."""
        async for chunk in super().astream(input, config, stop=stop, api_key=_key_of(api_key, config),
                                           **kwargs):
            yield chunk

    def bind_tools(self, tools: Any, **kwargs: Any) -> Any:
        """Binds *tools*, formatted as ``ChatOpenAI`` formats them, to this model."""
        return self.bind(**self._own.bind_tools(tools, **kwargs).kwargs)

    # === What BaseChatModel calls ======================================================

    async def _agenerate(self, messages: List[BaseMessage], stop: Optional[List[str]] = None,
                         run_manager: Optional[AsyncCallbackManagerForLLMRun] = None, *,
                         api_key: Optional[Secret] = None, **kwargs: Any) -> ChatResult:
        result = await self._for(api_key)._agenerate(messages, stop=stop, run_manager=run_manager, **kwargs)
        return result  # type: ignore[no-any-return]

    async def _astream(self, messages: List[BaseMessage], stop: Optional[List[str]] = None,
                       run_manager: Optional[AsyncCallbackManagerForLLMRun] = None, *,
                       api_key: Optional[Secret] = None, **kwargs: Any) -> AsyncIterator[ChatGenerationChunk]:
        async for chunk in self._for(api_key)._astream(messages, stop=stop, run_manager=run_manager,
                                                       **kwargs):
            yield chunk

    def _generate(self, messages: List[BaseMessage], stop: Optional[List[str]] = None,
                  run_manager: Optional[CallbackManagerForLLMRun] = None, **kwargs: Any) -> ChatResult:
        raise NotImplementedError("%s is asynchronous only: use ainvoke or astream" % type(self).__name__)

    def _stream(self, messages: List[BaseMessage], stop: Optional[List[str]] = None,
                run_manager: Optional[CallbackManagerForLLMRun] = None,
                **kwargs: Any) -> Iterator[ChatGenerationChunk]:
        raise NotImplementedError("%s is asynchronous only: use ainvoke or astream" % type(self).__name__)

    # === Which model answers ===========================================================

    def _for(self, api_key: Optional[Secret]) -> Any:
        """The endpoint's own model, or one built for this call with *api_key*."""
        if api_key is None:
            return self._own

        async def given() -> str:
            return api_key.reveal()

        return self._openai(given)

    def _openai(self, key: Any) -> Any:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=self._model, base_url=self._base_url, api_key=key)


def _key_of(api_key: Optional[Secret], config: Optional[RunnableConfig]) -> Optional[Secret]:
    """The parameter when given, else the key the run's configuration carries, else None."""
    if api_key is not None:
        return api_key
    carried = ensure_config(config).get("configurable", {}).get("api_key")
    return carried if isinstance(carried, Secret) else None
