"""
Tests for installing and running the hive: behind chatinho[hive], and nothing of it in the core.
"""

import subprocess
import sys
import time
import urllib.error
import urllib.request

from fakes.hive import free_port

_BLOCK = """
import builtins
real = builtins.__import__
def blocked(name, *a, **k):
    if name.split(".")[0] in %r:
        raise ImportError("No module named %%r" %% name)
    return real(name, *a, **k)
builtins.__import__ = blocked
"""


def run(script: str, blocked=()) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-c", (_BLOCK % (tuple(blocked),)) + script],
                          capture_output=True, text=True)


# @ac AC-HIVE-010.1
def test_without_the_extra_the_hive_names_it():
    done = run(
        "try:\n"
        "    import chatinho.hive\n"
        "except ImportError as exc:\n"
        "    print('refused:', exc)\n",
        blocked=("fastapi",),
    )
    assert done.returncode == 0, done.stderr
    assert done.stdout.startswith("refused:")
    assert "chatinho[hive]" in done.stdout


# @ac AC-HIVE-010.2
def test_the_core_loads_none_of_the_hives_libraries():
    done = run(
        "import sys, chatinho\n"
        "from chatinho import HiveBackend\n"
        "print(sorted(m for m in ('fastapi', 'uvicorn', 'sqlalchemy') if m in sys.modules))\n"
    )
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "[]"


# @ac AC-HIVE-010.3
def test_serving_answers_on_its_port(tmp_path):
    port = free_port()
    db   = "sqlite:///%s" % (tmp_path / "hive.db")
    argv = [sys.executable, "-m", "chatinho.hive.cli", "serve", "--port", str(port), "--db", db]
    proc = subprocess.Popen(argv,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        deadline = time.monotonic() + 20
        while True:
            try:
                with urllib.request.urlopen("http://127.0.0.1:%d/" % port, timeout=1) as answer:
                    assert answer.status == 200
                    break
            except OSError:
                if proc.poll() is not None or time.monotonic() > deadline:
                    out = proc.stdout.read().decode() if proc.stdout else ""
                    raise AssertionError("the hive did not answer: %s" % out)
                time.sleep(0.2)
    finally:
        proc.terminate()
        proc.wait(timeout=10)


# The admin key rides on the stream's query string (a browser's EventSource sets no headers), and
# uvicorn's access log writes every path with its query: the served log must hold it masked.
def test_the_access_log_never_holds_a_key_from_the_query(tmp_path):
    port = free_port()
    db   = "sqlite:///%s" % (tmp_path / "hive.db")
    key  = "hive_" + "ab" * 24
    argv = [sys.executable, "-m", "chatinho.hive.cli", "serve", "--port", str(port), "--db", db]
    proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        deadline = time.monotonic() + 20
        while True:
            try:
                stream = "http://127.0.0.1:%d/api/chats/team/stream?key=%s" % (port, key)
                urllib.request.urlopen(stream, timeout=1)
            except urllib.error.HTTPError as refused:
                assert refused.code == 401
                break
            except OSError:
                if proc.poll() is not None or time.monotonic() > deadline:
                    raise AssertionError("the hive did not answer")
                time.sleep(0.2)
    finally:
        proc.terminate()
        output = proc.communicate(timeout=10)[0].decode()
    assert "/api/chats/team/stream?key=***" in output
    assert key not in output
