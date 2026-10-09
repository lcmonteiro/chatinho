"""Where the public names live, and the two builders.

The core is unprefixed, each frontend lives under ``chatinho.frontends``, and
each builder needs only its own extra. See openspec/specs/package-layout.
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


def test_the_chat_builder_escapes_newlines_like_the_composer():
    import inspect
    from chatinho.frontends.chat.composer import NEWLINE_ESCAPE
    default = inspect.signature(build_chat_session).parameters["newline_escape"].default
    assert default == NEWLINE_ESCAPE


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


# === Each builder needs only its own extra ========================================

_WITH_ONE_EXTRA_BLOCKED = """
import builtins, sys
blocked_root = sys.argv[1]
real = builtins.__import__
def blocked(name, *a, **k):
    if name.split(".")[0] == blocked_root:
        raise ImportError("No module named %r" % name)
    return real(name, *a, **k)
builtins.__import__ = blocked

import chatinho
for name in ("build_chat_session", "build_mcp_session"):
    try:
        builder = getattr(chatinho, name)
    except ImportError as exc:
        print(name, "missing", str(exc))
    else:
        print(name, "ok")
"""


def _read_builders_without(root: str) -> str:
    done = subprocess.run(
        [sys.executable, "-c", _WITH_ONE_EXTRA_BLOCKED, root],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    assert done.returncode == 0, done.stderr
    return done.stdout


def test_the_terminal_builder_does_not_need_the_mcp_extra():
    out = _read_builders_without("fastmcp")
    assert "build_chat_session ok" in out
    assert "build_mcp_session missing" in out and "chatinho[mcp]" in out


def test_the_mcp_builder_does_not_need_the_tui_extra():
    out = _read_builders_without("textual")
    assert "build_mcp_session ok" in out
    assert "build_chat_session missing" in out and "chatinho[tui]" in out


def test_building_a_terminal_chat_never_imports_the_mcp_library():
    done = subprocess.run(
        [sys.executable, "-c",
         "import sys; from chatinho import build_chat_session; build_chat_session(); "
         "print('fastmcp' in sys.modules)"],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "False"
