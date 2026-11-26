"""
EndpointModel: the one model every component calls, with a key per call.

The OpenAI client is the stub of ``fakes.llm``, patched where the model kit
builds its clients: the only place in chatinho that does.
"""

import ast
import asyncio
import os
import pathlib
import subprocess
import sys
import textwrap
from typing import Callable, List

import pytest

from chatinho import ChatMessage, MessageID, Endpoint, Env, File, KeyUnavailable, Secret
from chatinho.support.kits.model import EndpointModel, lent_key
from chatinho.support.kits.model import endpoint as module

from fakes.llm import FakeOpenAI


@pytest.fixture(autouse=True)
def fake(monkeypatch):
    FakeOpenAI.reset()
    monkeypatch.setattr(module, "AsyncOpenAI", FakeOpenAI)
    return FakeOpenAI


HI = [{"role": "user", "content": "hi"}]


def _requests() -> List[dict]:
    return [r for c in FakeOpenAI.clients for r in c.requests]


async def _until(condition: Callable[[], bool]) -> None:
    """Waits up to a second for *condition*, then fails rather than hang."""
    for _ in range(100):
        if condition():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("timed out waiting")


# === A call is made with its own key or the endpoint's ==============================

# @ac AC-MODEL-001.1
async def test_a_key_on_the_call_then_its_own():
    model = EndpointModel(Endpoint(model="m", api_key="sk-own"))
    await model.complete(HI, api_key=Secret("sk-call"))
    await model.complete(HI)
    lent, own = FakeOpenAI.clients
    assert (lent.api_key, own.api_key) == ("sk-call", "sk-own")
    assert lent.closed and not own.closed
    assert [r["model"] for r in _requests()] == ["m", "m"]


# @ac AC-MODEL-001.2
async def test_no_key_at_all():
    model = EndpointModel(Endpoint(model="m"))
    assert not model.has_own_key
    with pytest.raises(KeyUnavailable):
        await model.complete(HI)
    assert FakeOpenAI.clients == []


# @ac AC-MODEL-001.3
async def test_a_source_that_cannot_read(monkeypatch):
    monkeypatch.delenv("MODEL_TEST_KEY", raising=False)
    model = EndpointModel(Endpoint(api_key=Env("MODEL_TEST_KEY")))
    with pytest.raises(KeyUnavailable, match="MODEL_TEST_KEY"):
        await model.complete(HI)
    assert _requests() == []


# @ac AC-MODEL-001.4
async def test_headers_with_either_key():
    model = EndpointModel(Endpoint(api_key="sk-own"), headers={"Editor-Version": "v1"})
    await model.complete(HI)
    await model.complete(HI, api_key=Secret("sk-call"))
    assert [c.default_headers for c in FakeOpenAI.clients] == [{"Editor-Version": "v1"}] * 2


# @ac AC-MODEL-001.5
async def test_read_late_never_shown():
    reads: List[int] = []

    def secret() -> str:
        reads.append(1)
        return "sk-secret"

    model = EndpointModel(Endpoint(api_key=secret))
    assert reads == []
    await model.complete(HI)
    assert reads and FakeOpenAI.clients[0].api_key == "sk-secret"
    assert "sk-secret" not in repr(model)


# === Its own key keeps one client, following the key =================================

# @ac AC-MODEL-002.1
async def test_calls_at_once_share_one_client():
    FakeOpenAI.gate = asyncio.Event()
    model = EndpointModel(Endpoint(api_key="sk-own"))
    calls = asyncio.gather(*(model.complete(HI) for _ in range(3)))
    await _until(lambda: len(_requests()) == 3)
    FakeOpenAI.gate.set()
    answers = await asyncio.wait_for(calls, timeout=2)
    assert [a.choices[0].message.content for a in answers] == ["Sunny"] * 3
    assert len(FakeOpenAI.clients) == 1


# @ac AC-MODEL-002.2
@pytest.mark.skipif(os.name != "posix", reason="POSIX permissions")
async def test_a_rotated_out_client(tmp_path):
    path = tmp_path / "model.key"
    path.write_text("sk-one")
    path.chmod(0o600)
    model = EndpointModel(Endpoint(api_key=File(path)))
    FakeOpenAI.gate = asyncio.Event()
    first = asyncio.create_task(model.complete(HI))
    await _until(lambda: len(_requests()) == 1)
    path.write_text("sk-two")
    second = asyncio.create_task(model.complete(HI))
    await _until(lambda: len(_requests()) == 2)
    old, new = FakeOpenAI.clients
    assert (old.api_key, new.api_key) == ("sk-one", "sk-two")
    assert not old.closed                            # still answering the first call
    FakeOpenAI.gate.set()
    await asyncio.gather(first, second)
    assert old.closed and not new.closed


# @ac AC-MODEL-002.3
async def test_closed():
    used, unused = EndpointModel(Endpoint(api_key="sk-own")), EndpointModel(Endpoint(api_key="sk-own"))
    await used.complete(HI)
    own, = FakeOpenAI.clients
    await used.close()
    await unused.close()
    assert own.closed


# === The key a message lends ========================================================

# @ac AC-MODEL-004.1
def test_the_key_a_message_lends():
    lends = {"llm": Secret("sk-a"), "other": Secret("sk-b")}
    msg   = ChatMessage(id=MessageID.new(), text="hi", credentials=lends)
    lent = lent_key(msg, "llm")
    assert lent is not None and lent.reveal() == "sk-a"
    assert lent_key(msg, "missing") is None
    assert lent_key(ChatMessage(id=MessageID.new(), text="hi"), "llm") is None


# === LangChain only for the LangChain face ==========================================

# @ac AC-MODEL-005.1
def test_without_langchain():
    script = textwrap.dedent("""
        import asyncio, importlib.abc, sys

        class Block(importlib.abc.MetaPathFinder):
            def find_spec(self, name, path=None, target=None):
                if name.split(".")[0] in ("langchain_core", "langchain_openai", "langchain"):
                    raise ImportError("blocked: " + name)

        sys.meta_path.insert(0, Block())
        sys.path.insert(0, %r)
        from fakes.llm import FakeOpenAI
        from chatinho import Endpoint
        from chatinho.support.kits.model import EndpointModel
        from chatinho.support.kits.model import endpoint
        endpoint.AsyncOpenAI = FakeOpenAI
        model = EndpointModel(Endpoint(api_key="sk-own"))
        answer = asyncio.run(model.complete([{"role": "user", "content": "hi"}]))
        print(answer.choices[0].message.content)
        try:
            model.chat_model()
        except ImportError as exc:
            print("refused:", exc)
    """) % str(pathlib.Path(__file__).resolve().parents[1])
    out = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    lines = out.stdout.splitlines()
    assert lines[0] == "Sunny"
    assert lines[1].startswith("refused:") and "chatinho[langchain]" in lines[1]


# === Every component calls a model through it =======================================

#: What builds a client or a chat model on an OpenAI-compatible endpoint.
CLIENTS = {"AsyncOpenAI", "OpenAI", "ChatOpenAI"}


# @ac AC-MODEL-006.1
def test_one_door():
    src   = pathlib.Path(module.__file__).resolve().parents[3]
    door  = src / "support" / "kits" / "model"
    found = {}
    for path in sorted(src.rglob("*.py")):
        if door in path.parents:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom):
                names = {alias.name for alias in node.names} & CLIENTS
                if names:
                    found[path.relative_to(src).as_posix()] = sorted(names)
    assert found == {}, "only the model kit may build a model client: %s" % found
