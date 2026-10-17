"""Where the public names live, and the two builders.

The core is unprefixed, each frontend lives under ``chatinho.frontends``, and
each builder needs only its own frontend's extra. See openspec/specs/package-layout.
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


# === Each builder needs only its own extra ========================================

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
for name in ("build_chat_session", "build_mcp_session", "ChatFrontend", "McpFrontend", "AgentConnector"):
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


_BLOCKING = """
import builtins, sys
blocked_roots = set(sys.argv[1].split(","))
real = builtins.__import__
def blocked(name, *a, **k):
    if name.split(".")[0] in blocked_roots:
        raise ImportError("No module named %r" % name)
    return real(name, *a, **k)
builtins.__import__ = blocked
"""


def _run_without(roots: str, code: str) -> str:
    """Runs *code* with the libraries in *roots* (comma-separated) unimportable; its stdout."""
    done = subprocess.run([sys.executable, "-c", _BLOCKING + code, roots],
                          capture_output=True, text=True, cwd=str(ROOT))
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


def test_the_terminal_builder_needs_only_the_terminal():
    built = _run_without("fastmcp", "import chatinho\n"
                         "s = chatinho.build_chat_session()\n"
                         "print(type(s.frontend).__name__)")
    assert built == "ChatFrontend"


def test_the_mcp_builder_needs_only_mcp():
    built = _run_without("textual", "import chatinho\n"
                         "s = chatinho.build_mcp_session(token='t')\n"
                         "print(type(s.frontend).__name__)")
    assert built == "McpFrontend"


@pytest.mark.parametrize("library, call, extra", [
    ("textual", "build_chat_session()", "chatinho[tui]"),
    ("fastmcp", "build_mcp_session(token='t')", "chatinho[mcp]"),
])
def test_a_builder_without_its_library_names_its_own_extra(library, call, extra):
    """Reading it is fine; calling it imports its frontend, and that is where the extra is named."""
    said = _run_without(library, "import chatinho\n"
                        "try:\n"
                        "    chatinho.%s\n"
                        "except ImportError as exc:\n"
                        "    print(exc)\n" % call)
    assert extra in said and "tui,mcp" not in said


def test_the_builder_module_needs_neither_extra():
    said = _run_without("textual,fastmcp", "import chatinho.builder as b\n"
                        "print(callable(b.build_chat_session) and callable(b.build_mcp_session))")
    assert said == "True"
    assert chatinho.builder.build_chat_session is chatinho.build_chat_session


def test_the_builders_newline_escape_is_the_terminals():
    """Written out in builder.py so it need not import the terminal; this keeps the two equal."""
    from chatinho.builder import NEWLINE_ESCAPE as builders
    from chatinho.frontends.chat.composer import NEWLINE_ESCAPE as terminals
    assert builders == terminals


def test_each_frontend_needs_only_its_own_extra():
    without_mcp = _read_without("fastmcp")
    assert without_mcp["ChatFrontend"] == ["ok"]
    assert "chatinho[mcp]" in without_mcp["McpFrontend"][1]

    without_tui = _read_without("textual")
    assert without_tui["McpFrontend"] == ["ok"]
    assert "chatinho[tui]" in without_tui["ChatFrontend"][1]


def test_the_agent_connector_needs_its_extra():
    status, message = _read_without("langchain")["AgentConnector"]
    assert status == "missing"
    assert "chatinho[langchain]" in message
    assert _read_without("textual")["AgentConnector"] == ["ok"]


def test_the_core_stays_light():
    done = subprocess.run(
        [sys.executable, "-c",
         "import sys, chatinho, chatinho.connectors; "
         "print(sorted(m for m in sys.modules if m.split('.')[0].startswith('lang')))"],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "[]"
