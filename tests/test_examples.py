"""
Every demo in examples/, built headless against a stubbed model and run once.

Each LLM demo exposes ``parts()``, the connectors, commands and backend its
``main()`` hands to a builder; here they go to a ``ChatSession`` with a
:class:`~conftest.Driver` instead of a terminal. No key and no network.
"""

import asyncio
import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import urllib.error
import urllib.request

import pytest
from fastmcp import Client

import chatinho
from chatinho import ChatSession, Reply
from chatinho.connectors import openai as module
from chatinho.connectors.mcp import McpConnector
from chatinho.frontends.mcp import McpFrontend

from conftest import Driver, driven
from fakes.llm import FakeOpenAI, requests, sent

EXAMPLES = pathlib.Path(__file__).resolve().parent.parent / "examples"


def example(name: str):
    """Imports ``examples/<name>.py`` as a module, without running its main."""
    spec = importlib.util.spec_from_file_location("example_%s" % name, EXAMPLES / ("%s.py" % name))
    assert spec is not None and spec.loader is not None
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


@pytest.fixture(autouse=True)
def llm(monkeypatch):
    """A key in the environment and the stub in place of AsyncOpenAI."""
    FakeOpenAI.reset()
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("CHATINHO_MODEL", raising=False)
    monkeypatch.delenv("CHATINHO_BASE_URL", raising=False)
    monkeypatch.delenv("CHATINHO_PROFILE", raising=False)
    monkeypatch.setenv("CHATINHO_PROFILES", os.devnull + ".missing")   # no profiles file
    monkeypatch.setenv("XDG_CONFIG_HOME", os.devnull + ".missing")
    monkeypatch.setattr(module, "AsyncOpenAI", FakeOpenAI)
    return FakeOpenAI


async def headless(parts: dict):
    """A started session made of a demo's parts, with a Driver as the frontend."""
    view    = Driver()
    session = ChatSession(frontend=view, **parts)
    await session.start()
    return session, view


async def reply_to(view, said):
    for _ in range(300):
        for m in view.context():
            if m.reply_to == said:
                return m
        await asyncio.sleep(0.01)
    raise AssertionError("no reply to %s" % said)


async def until_requests(count: int) -> None:
    for _ in range(300):
        if len(requests()) >= count:
            return
        await asyncio.sleep(0.01)
    raise AssertionError("the model was asked %d times, not %d" % (len(requests()), count))


# === assistant.py =================================================================

async def test_the_assistant_answers_and_remembers_across_sessions(tmp_path, monkeypatch):
    monkeypatch.setenv("CHATINHO_DB", str(tmp_path / "assistant.db"))
    assistant = example("assistant")

    session, view = await headless(assistant.parts())
    FakeOpenAI.reply = "Hi Ana"
    reply = await reply_to(view, await view.say("My name is Ana"))
    assert reply.text == "Hi Ana"
    assert requests()[-1]["model"] == "gpt-4o-mini"
    await session.close()

    session, view = await headless(assistant.parts())
    FakeOpenAI.reply = "Ana"
    await reply_to(view, await view.say("What is my name?"))
    turns = [m for m in sent() if m["role"] != "system"]
    assert turns == [
        {"role": "user",      "content": "My name is Ana"},
        {"role": "assistant", "content": "Hi Ana"},
        {"role": "user",      "content": "What is my name?"},
    ]
    await session.close()


async def test_a_profile_picks_the_endpoint_and_model(tmp_path, monkeypatch):
    profiles = tmp_path / "profiles.toml"
    profiles.write_text('[local]\nbase_url = "http://localhost:11434/v1"\nmodel = "qwen"\n'
                        'api_key = "literal:ollama"\n')
    profiles.chmod(0o600)
    monkeypatch.setenv("CHATINHO_PROFILES", str(profiles))
    monkeypatch.setenv("CHATINHO_PROFILE", "local")
    monkeypatch.delenv("OPENAI_API_KEY")
    monkeypatch.setenv("CHATINHO_DB", str(tmp_path / "assistant.db"))
    session, view = await headless(example("assistant").parts())
    try:
        await reply_to(view, await view.say("hi"))
        client = FakeOpenAI.clients[-1]
        assert (client.base_url, client.api_key, client.requests[-1]["model"]) == (
            "http://localhost:11434/v1", "ollama", "qwen")
    finally:
        await session.close()


# === team.py ======================================================================

async def test_the_reviewer_sees_what_the_coder_wrote():
    session, view = await headless(example("team").parts())
    try:
        FakeOpenAI.reply = "def add(a, b): return a + b"
        await reply_to(view, await view.say("write add", to=view.id_of("coder")))
        FakeOpenAI.reply = "Looks fine."
        await reply_to(view, await view.say("review it", to=view.id_of("reviewer")))
        assert {"role": "user", "content": "coder: def add(a, b): return a + b"} in sent()
        assert sent()[-1] == {"role": "user", "content": "review it"}
    finally:
        await session.close()


# === agent.py =====================================================================

async def test_the_lead_asks_the_coder_and_answers():
    from fakes.agent import calls, fake

    parts = example("agent").parts()
    lead  = parts["connectors"][0]
    lead.model = fake(calls("ask_coder", question="write add", then=lambda code: "Here it is:\n" + code))
    session, view = await headless(parts)
    try:
        FakeOpenAI.reply = "def add(a, b): return a + b"
        answer = await view.ask(lead.peer_id, "I need an add function")
        assert answer.text == "Here it is:\n%s" % Reply("def add(a, b): return a + b")
        assert sent()[-1] == {"role": "user", "content": "write add"}
        assert lead.model.tools[-1] == ["ask_coder", "run_help"]
    finally:
        await session.close()


async def test_the_lead_responds_to_what_you_say():
    from fakes.agent import fake, says

    parts = example("agent").parts()
    lead  = parts["connectors"][0]
    lead.model = fake(says("On it."))
    session, view = await headless(parts)
    try:
        said = await view.say("I need an add function")
        for _ in range(200):
            response = [m for m in view.context() if m.frm == lead.peer_id]
            if response:
                break
            await asyncio.sleep(0.01)
        assert [(m.text, m.reply_to) for m in response] == [("On it.", said)]
    finally:
        await session.close()


# === files.py =====================================================================

async def test_read_sends_the_file_and_the_question(tmp_path):
    notes = tmp_path / "notes.md"
    notes.write_text("- ship on Friday\n- who owns the release?\n", encoding="utf-8")
    session, view = await headless(example("files").parts())
    try:
        assert await view.command("read", "%s what is open?" % notes) is None
        await until_requests(1)
        question = sent()[-1]["content"]
        assert question.startswith("what is open?")
        assert "who owns the release?" in question
        assert any(m.frm == view.id_of("assistant") and m.text == "Sunny"
                   for m in await _settled(view))
    finally:
        await session.close()


async def test_read_takes_a_quoted_path_with_spaces(tmp_path):
    notes = tmp_path / "my notes.md"
    notes.write_text("ship on Friday", encoding="utf-8")
    session, view = await headless(example("files").parts())
    try:
        assert await view.command("read", '"%s" when do we ship?' % notes) is None
        await until_requests(1)
        question = sent()[-1]["content"]
        assert question.startswith("when do we ship?") and "ship on Friday" in question
    finally:
        await session.close()


async def _settled(view):
    for _ in range(300):
        if any(m.text == "Sunny" for m in view.context()):
            break
        await asyncio.sleep(0.01)
    return view.context()


@pytest.mark.parametrize("make, why", [
    (lambda p: p,                                                   "is not a file"),
    (lambda p: _write(p / "big.txt", b"x" * (64 * 1024 + 1)),       "larger than 64 KB"),
    (lambda p: _write(p / "blob.bin", b"\xff\xfe\x00binary"),        "not UTF-8"),
])
async def test_read_refuses_without_asking_the_model(tmp_path, make, why):
    session, view = await headless(example("files").parts())
    try:
        answer = await view.command("read", str(make(tmp_path)))
        assert answer.startswith("read: ") and why in answer
        await asyncio.sleep(0.05)
        assert requests() == []
    finally:
        await session.close()


def _write(path: pathlib.Path, data: bytes) -> pathlib.Path:
    path.write_bytes(data)
    return path


# === A missing key ================================================================

@pytest.mark.parametrize("name", ["assistant", "team", "files", "lab_client", "agent"])
def test_no_key_exits_with_a_hint(name, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY")
    demo = example(name)
    monkeypatch.setattr(demo, "build_chat_session", _no_ui)
    with pytest.raises(SystemExit) as exited:
        demo.main()
    assert str(exited.value) == "OPENAI_API_KEY is not set; see examples/README.md"


def _no_ui(**kwargs):
    raise AssertionError("the UI started without a key")


# === The lab pair =================================================================

async def lab():
    """lab_server's parts, served by an in-process McpFrontend."""
    front   = McpFrontend(token="t", credentials=example("lab_server").CREDENTIALS)
    session = ChatSession(frontend=front, **example("lab_server").parts())
    await session.start()
    return session, front


async def test_the_lab_answers_with_the_clients_key():
    there, front = await lab()
    key   = os.environ["OPENAI_API_KEY"]
    here, view   = await headless(example("lab_client").parts(server=front.server))
    try:
        reply = await reply_to(view, await view.say("what is MCP?"))
        assert reply.text == "Sunny"
        assert [c.api_key for c in FakeOpenAI.clients if c.requests] == [key]
        assert all(c.closed for c in FakeOpenAI.clients if c.requests)
    finally:
        await here.close()
        await there.close()


async def test_the_lab_without_a_lent_key_says_so():
    there, front = await lab()
    session, view = await driven(connectors=[McpConnector(server=front.server, name="lab")])
    try:
        reply = await reply_to(view, await view.say("hello"))
        assert "no API key" in reply.text
        assert requests() == []
    finally:
        await session.close()
        await there.close()


async def test_a_plain_fastmcp_client_asks_the_lab(capsys):
    there, front = await lab()
    try:
        await example("lab_fastmcp_client").talk(Client(front.server), "what is MCP?", "sk-lent")
        assert capsys.readouterr().out.splitlines() == ["peer: lab (answers)", "answered - Sunny"]
        assert [c.api_key for c in FakeOpenAI.clients if c.requests] == ["sk-lent"]
    finally:
        await there.close()


# === inbox.py =====================================================================

async def asked_over_http(timeout: float, answers=()):
    """Starts the inbox on a free port and POSTs a question; the status and body."""
    inbox   = example("inbox").InboxConnector(port=0, timeout=timeout)
    view    = Driver(answers=list(answers))
    session = ChatSession(frontend=view, connectors=[inbox])
    await session.start()
    serving = asyncio.create_task(inbox.serve())     # run() would; start() does not
    try:
        for _ in range(200):
            if inbox._server is not None:
                break
            await asyncio.sleep(0.01)

        def post():
            request = urllib.request.Request("http://127.0.0.1:%d/ask" % inbox.port,
                                             data=json.dumps({"text": "Deploy?"}).encode())
            direct  = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            try:
                with direct.open(request, timeout=10) as response:
                    return response.status, json.loads(response.read())
            except urllib.error.HTTPError as error:
                return error.code, json.loads(error.read())

        return await asyncio.get_running_loop().run_in_executor(None, post), view
    finally:
        serving.cancel()
        await session.close()


async def test_the_inbox_waits_for_the_answer():
    (status, body), view = await asked_over_http(5, answers=["yes"])
    assert (status, body) == (200, {"answer": "yes"})
    assert [m.text for m in view.asked] == ["Deploy?"]


async def test_the_inbox_gives_up_after_its_timeout():
    (status, _), _ = await asked_over_http(0.2)
    assert status == 504


# === hooks.py =====================================================================

def test_the_reference_example_reaches_every_hook():
    run = subprocess.run([sys.executable, str(EXAMPLES / "hooks.py")],
                         capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr
    hooks = [name for name in chatinho.__all__ if name.startswith("Hook") and name != "Hook"]
    assert len(hooks) == 15
    assert [h for h in hooks if h not in run.stdout] == []
