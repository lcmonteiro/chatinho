"""
The model's LangChain face: a key per call, from the call or the run's configuration.

Against a real OpenAI-compatible server on a local port (``fakes.llm_server``),
so the key each request carries is what ``ChatOpenAI`` and the OpenAI client
really sent.
"""

import asyncio
from typing import Any, Optional

import pytest

from chatinho import Endpoint, Literal, Secret
from chatinho.support.kits.model import EndpointModel

from fakes.llm_server import answers, serve_chat


def weather(city: str) -> str:
    """The weather in a city."""
    return "sunny in %s" % city


def _model_of(base_url: str, own: Optional[str] = "sk-own") -> Any:
    endpoint = Endpoint(base_url=base_url, model="m", api_key=Literal(own) if own else None)
    return EndpointModel(endpoint).chat_model()


# @ac AC-MODEL-003.1
async def test_a_key_on_the_call():
    async with serve_chat(answers("fine")) as server:
        model = _model_of(server.base_url)
        first  = await model.ainvoke("hi", api_key=Secret("sk-call"))
        second = await model.ainvoke("hi")
    assert (first.content, second.content) == ("fine", "fine")
    assert server.keys == ["sk-call", "sk-own"]


# @ac AC-MODEL-003.2
async def test_a_key_in_the_runs_configuration():
    config = {"configurable": {"api_key": Secret("sk-config")}}
    async with serve_chat(answers("fine")) as server:
        model = _model_of(server.base_url)
        await model.ainvoke("hi", config)
        await model.ainvoke("hi", config, api_key=Secret("sk-call"))
    assert server.keys == ["sk-config", "sk-call"]


# @ac AC-MODEL-003.3
async def test_bound_tools_keep_it():
    async with serve_chat(answers("fine")) as server:
        bound = _model_of(server.base_url).bind_tools([weather])
        await bound.ainvoke("hi", api_key=Secret("sk-call"))
    assert server.keys == ["sk-call"]
    assert [t["function"]["name"] for t in server.bodies[0]["tools"]] == ["weather"]


# @ac AC-MODEL-003.4
async def test_nothing_kept():
    async with serve_chat(answers("fine")) as server:
        model = _model_of(server.base_url, own=None)
        await model.ainvoke("hi", api_key=Secret("sk-call-secret"))
    assert server.keys == ["sk-call-secret"]
    assert "sk-call-secret" not in repr(model)
    seen = repr(vars(model)) + repr(getattr(model, "__pydantic_private__", None))
    assert "sk-call-secret" not in seen


# @ac AC-MODEL-003.5
async def test_asynchronous_only():
    async with serve_chat(answers("fine")) as server:
        model = _model_of(server.base_url)
        with pytest.raises(NotImplementedError):
            await asyncio.to_thread(model.invoke, "hi")
    assert server.keys == []
