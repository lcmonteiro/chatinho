"""What the LLM tests share: a stubbed AsyncOpenAI that records every client and request."""

import asyncio
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import openai


def failure(kind: str, text: str = "") -> Exception:
    """An SDK error of the given class name, built without a transport."""
    return type(kind, (openai.OpenAIError,), {})(text)


class FakeOpenAI:
    """Stands in for AsyncOpenAI: records every client and every request."""

    clients : List["FakeOpenAI"] = []
    reply   : str = "Sunny"
    error   : Optional[Exception] = None
    gate    : Optional[asyncio.Event] = None

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None) -> None:
        self.api_key  = api_key
        self.base_url = base_url
        self.requests : List[Dict[str, Any]] = []
        self.closed   = False
        self.chat     = SimpleNamespace(completions=SimpleNamespace(create=self._create))
        FakeOpenAI.clients.append(self)

    async def _create(self, **params: Any) -> Any:
        self.requests.append(params)
        if FakeOpenAI.gate is not None:
            await FakeOpenAI.gate.wait()
        if FakeOpenAI.error is not None:
            raise FakeOpenAI.error
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=FakeOpenAI.reply))])

    async def __aenter__(self) -> "FakeOpenAI":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        self.closed = True

    async def close(self) -> None:
        self.closed = True

    @classmethod
    def reset(cls) -> None:
        """Forgets every client and restores the defaults."""
        cls.clients = []
        cls.reply   = "Sunny"
        cls.error   = None
        cls.gate    = None


def requests() -> List[Dict[str, Any]]:
    """Every request any client made, oldest first."""
    return [r for c in FakeOpenAI.clients for r in c.requests]


def sent() -> List[Dict[str, str]]:
    """The messages of the last request."""
    return requests()[-1]["messages"]
