"""
LLMRouter sits behind chatinho[openai]: the core and the routers import without it.

See src/chatinho/routers/docs/spec.md.
"""

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent

_BLOCK_OPENAI = """
import builtins, sys
real = builtins.__import__
def blocked(name, *a, **k):
    if name.split(".")[0] == "openai":
        raise ImportError("No module named %r" % name)
    return real(name, *a, **k)
builtins.__import__ = blocked
"""


def run(script: str) -> subprocess.CompletedProcess:
    """Runs *script* in a fresh interpreter with ``openai`` blocked."""
    return subprocess.run([sys.executable, "-c", _BLOCK_OPENAI + script],
                          capture_output=True, text=True, cwd=str(ROOT))


# @ac AC-ROUTE-011.1
def test_the_core_and_the_routers_import_without_openai():
    done = run(
        "import chatinho, chatinho.routers\n"
        "from chatinho.routers import SimpleRouter\n"
        "print(SimpleRouter.__name__, 'openai' in sys.modules)\n"
    )
    assert done.returncode == 0, done.stderr
    assert done.stdout.split() == ["SimpleRouter", "False"]


# @ac AC-ROUTE-011.2
def test_reading_it_without_openai_names_the_extra():
    done = run(
        "import chatinho\n"
        "try:\n"
        "    chatinho.LLMRouter\n"
        "except ImportError as exc:\n"
        "    print('refused:', exc)\n"
    )
    assert done.returncode == 0, done.stderr
    assert done.stdout.startswith("refused:")
    assert "chatinho[openai]" in done.stdout


# @ac AC-ROUTE-011.3
def test_it_is_one_class_wherever_it_is_read():
    import chatinho
    import chatinho.routers
    from chatinho.routers.llm import LLMRouter

    assert chatinho.LLMRouter is chatinho.routers.LLMRouter is LLMRouter
