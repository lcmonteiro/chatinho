"""Where the public names live, and the two builders.

The core is unprefixed, each frontend lives under ``chatinho.frontends``, and
the builders need both extras. See openspec/specs/package-layout.
"""

import importlib
import pathlib
import subprocess
import sys

import pytest

import chatinho
from chatinho import HelpCommand, HookAnswer, LOCAL, Reply, connector, require
from chatinho.builder import build_chat_session, build_mcp_session
from chatinho.frontends.chat import ChatFrontend
from chatinho.frontends.mcp import McpFrontend
from chatinho.session import ChatSession

ROOT = pathlib.Path(__file__).resolve().parent.parent


@connector("agent")
@require(HookAnswer)
class _Agent:
    async def answer(self, msg):
        return Reply("ok")


# === Import paths =================================================================

def test_the_core_imports_by_its_new_names():
    from chatinho.hooks import HookSay
    from chatinho.message import ChatMessage
    assert ChatSession is chatinho.ChatSession
    assert ChatMessage is chatinho.ChatMessage
    assert HookSay is chatinho.HookSay


@pytest.mark.parametrize("old", [
    "chat_session", "chat_message", "chat_hooks", "chat_app", "chat_log",
    "chat_input", "chat_style", "chat_clipboard", "chat_builder",
])
def test_the_old_module_names_are_gone(old):
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("chatinho." + old)


def test_the_terminal_is_the_chat_frontend_wherever_it_is_read():
    from chatinho.frontends import ChatFrontend as from_frontends
    assert chatinho.ChatFrontend is ChatFrontend is from_frontends
    assert not hasattr(chatinho, "ChatApp")
    assert not hasattr(chatinho, "build_chat")


def test_the_terminal_style_lives_with_the_terminal():
    from chatinho.frontends.chat.style import ChatStyle
    assert chatinho.ChatStyle is ChatStyle


# === Builders =====================================================================

def test_a_chat_with_a_terminal():
    session = build_chat_session(commands=[HelpCommand()], title="Demo")
    assert isinstance(session, ChatSession)
    assert isinstance(session.frontend, ChatFrontend)
    assert session.frontend.title == "Demo"
    assert session._peers()[LOCAL] is session.frontend
    assert "help" in session._commands()


def test_a_chat_served_over_mcp():
    agent   = _Agent()
    session = build_mcp_session(connectors=[agent], token="t", port=9000)
    assert isinstance(session, ChatSession)
    assert isinstance(session.frontend, McpFrontend)
    assert session.frontend.name == "master"
    assert session.frontend.port == 9000
    assert session._peers()[LOCAL] is session.frontend
    assert agent in session._peers().values()


def test_an_mcp_chat_without_a_token():
    with pytest.raises(ValueError):
        build_mcp_session(token="")


# === The builders need both extras ===============================================

_WITH_ONE_LIBRARY_BLOCKED = """
import builtins, sys
blocked_root = sys.argv[1]
real = builtins.__import__
def blocked(name, *a, **k):
    if name.split(".")[0] == blocked_root:
        raise ImportError("No module named %r" % name)
    return real(name, *a, **k)
builtins.__import__ = blocked

import chatinho
for name in ("build_chat_session", "build_mcp_session", "ChatFrontend", "McpFrontend"):
    try:
        getattr(chatinho, name)
    except ImportError as exc:
        print(name, "missing", str(exc).replace(" ", "_"))
    else:
        print(name, "ok")
"""


def _read_without(root: str) -> dict:
    done = subprocess.run(
        [sys.executable, "-c", _WITH_ONE_LIBRARY_BLOCKED, root],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    assert done.returncode == 0, done.stderr
    return {line.split()[0]: line.split()[1:] for line in done.stdout.splitlines()}


@pytest.mark.parametrize("library", ["textual", "fastmcp"])
def test_either_builder_needs_both_extras(library):
    read = _read_without(library)
    for builder in ("build_chat_session", "build_mcp_session"):
        status, message = read[builder]
        assert status == "missing"
        assert "chatinho[tui,mcp]" in message


def test_each_frontend_needs_only_its_own_extra():
    without_mcp = _read_without("fastmcp")
    assert without_mcp["ChatFrontend"] == ["ok"]
    assert "chatinho[mcp]" in without_mcp["McpFrontend"][1]

    without_tui = _read_without("textual")
    assert without_tui["McpFrontend"] == ["ok"]
    assert "chatinho[tui]" in without_tui["ChatFrontend"][1]
