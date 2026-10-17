"""
Key sources: where a key lives, read when needed, and never shown.

See openspec/specs/key-sources.
"""

import os
import sys
import types

import pytest

from chatinho import Secret
from chatinho.keys import Chain, Command, DotEnv, Env, File, Keyring, KeyUnavailable, Literal
from chatinho.keys import key, read_async, to_source

posix = pytest.mark.skipif(os.name != "posix", reason="POSIX permissions")


def private(path, text: str):
    path.write_text(text, encoding="utf-8")
    path.chmod(0o600)
    return path


# === Each source yields a Secret ==================================================

def test_from_the_environment(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", " sk-env\n")
    got = Env("OPENAI_API_KEY").read()
    assert isinstance(got, Secret) and got.reveal() == "sk-env"


def test_an_unset_variable(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(KeyUnavailable, match="OPENAI_API_KEY is not set"):
        Env("OPENAI_API_KEY").read()


def test_a_dotenv_variable(tmp_path):
    env = tmp_path / ".env"
    env.write_text('# settings\nexport OTHER=1\nOPENAI_API_KEY="sk-dot"\nPLAIN=v # note\n')
    assert DotEnv(env, "OPENAI_API_KEY").read().reveal() == "sk-dot"
    assert DotEnv(env, "PLAIN").read().reveal() == "v"
    with pytest.raises(KeyUnavailable, match="MISSING in"):
        DotEnv(env, "MISSING").read()


@posix
def test_a_private_file_and_a_rotated_key(tmp_path):
    path = private(tmp_path / "openai.key", "sk-one\n")
    source = File(path)
    assert source.read().reveal() == "sk-one"
    path.write_text("sk-two\n")
    assert source.read().reveal() == "sk-two"


@posix
def test_a_file_others_can_read_is_refused(tmp_path):
    path = tmp_path / "openai.key"
    path.write_text("sk-shared")
    path.chmod(0o644)
    with pytest.raises(KeyUnavailable) as refused:
        File(path).read()
    assert "chmod 600" in str(refused.value) and str(path) in str(refused.value)
    assert "sk-shared" not in str(refused.value)


def test_a_missing_file(tmp_path):
    with pytest.raises(KeyUnavailable, match="does not exist"):
        File(tmp_path / "nope").read()


# === Commands and the keychain read once ==========================================

def script(tmp_path, body: str):
    path = tmp_path / "secret.py"
    path.write_text(body)
    return [sys.executable, str(path)]


def test_a_command_runs_once(tmp_path):
    count = tmp_path / "count"
    argv  = script(tmp_path, "import pathlib\np = pathlib.Path(%r)\n"
                             "p.write_text(p.read_text() + 'x' if p.exists() else 'x')\n"
                             "print('sk-cmd')\n" % str(count))
    source = Command(argv)
    assert [source.read().reveal() for _ in range(3)] == ["sk-cmd"] * 3
    assert count.read_text() == "x"


def test_a_failing_command_hides_its_output(tmp_path):
    argv = script(tmp_path, "import sys\nprint('sk-partial')\nsys.exit(3)\n")
    with pytest.raises(KeyUnavailable) as failed:
        Command(argv).read()
    assert "exited 3" in str(failed.value) and "sk-partial" not in str(failed.value)


def test_a_missing_program():
    with pytest.raises(KeyUnavailable, match="not installed"):
        Command("no-such-program-for-chatinho").read()


def test_keyring_without_the_extra(monkeypatch):
    monkeypatch.setitem(sys.modules, "keyring", None)          # import keyring -> ImportError
    with pytest.raises(KeyUnavailable, match=r"chatinho\[keyring\]"):
        Keyring("chatinho", "openai").read()


def test_keyring_reads_once(monkeypatch):
    calls = []
    fake  = types.SimpleNamespace(get_password=lambda s, u: calls.append((s, u)) or "sk-ring")
    monkeypatch.setitem(sys.modules, "keyring", fake)
    source = Keyring("chatinho", "openai")
    assert source.read().reveal() == source.read().reveal() == "sk-ring"
    assert calls == [("chatinho", "openai")]


def test_keyring_without_the_entry(monkeypatch):
    monkeypatch.setitem(sys.modules, "keyring", types.SimpleNamespace(get_password=lambda s, u: None))
    with pytest.raises(KeyUnavailable, match="chatinho/openai: no such entry"):
        Keyring("chatinho", "openai").read()


# === A chain tries each in turn ===================================================

@posix
def test_the_first_that_yields(tmp_path, monkeypatch):
    monkeypatch.delenv("MISSING", raising=False)
    path = private(tmp_path / "k", "sk-file")
    assert Chain(Env("MISSING"), File(path)).read().reveal() == "sk-file"


def test_every_source_failed(monkeypatch):
    monkeypatch.delenv("A", raising=False)
    monkeypatch.delenv("B", raising=False)
    with pytest.raises(KeyUnavailable) as failed:
        Chain(Env("A"), Env("B")).read()
    assert "A is not set" in str(failed.value) and "B is not set" in str(failed.value)


# === Normalising what an argument was given =======================================

def test_a_plain_string_is_the_value(monkeypatch):
    monkeypatch.setenv("X", "from-env")
    assert to_source("env:X").read().reveal() == "env:X"


def test_a_function_and_a_secret():
    assert to_source(lambda: "sk-fn").read().reveal() == "sk-fn"
    assert to_source(Secret("sk-s")).read().reveal() == "sk-s"
    assert to_source(None) is None
    with pytest.raises(TypeError):
        to_source(42)


def test_a_literal_never_shows():
    assert "sk-lit" not in repr(Literal("sk-lit"))


async def test_read_async(tmp_path, monkeypatch):
    monkeypatch.setenv("K", "sk-a")
    assert (await read_async(Env("K"))).reveal() == "sk-a"
    argv = script(tmp_path, "print('sk-c')\n")
    assert (await read_async(Command(argv))).reveal() == "sk-c"


# === Reference strings ============================================================

@pytest.mark.parametrize("reference, kind, fields", [
    ("env:OPENAI_API_KEY",        Env,     {"name": "OPENAI_API_KEY"}),
    ("dotenv:conf/.env#KEY",      DotEnv,  {"name": "KEY"}),
    ("dotenv:#KEY",               DotEnv,  {"name": "KEY"}),
    ("keyring:chatinho/openai",   Keyring, {"service": "chatinho", "user": "openai"}),
    ("cmd:pass show 'api/open ai'", Command, {"argv": ["pass", "show", "api/open ai"]}),
])
def test_references(reference, kind, fields):
    parsed = key(reference)
    assert isinstance(parsed, kind)
    assert {name: getattr(parsed, name) for name in fields} == fields


def test_file_and_literal_references(tmp_path):
    assert key("dotenv:#KEY").path.name == ".env"
    assert key("file:~/k").path == key("file:~/k").path.expanduser()
    assert key("literal:ollama").read().reveal() == "ollama"


@pytest.mark.parametrize("reference", ["evn:OPENAI_API_KEY", "sk-abcdef", "keyring:only", "env:"])
def test_a_typo_is_not_a_key(reference):
    with pytest.raises(ValueError) as refused:
        key(reference)
    assert "env:" in str(refused.value) and "keyring:" in str(refused.value)
    assert "sk-abcdef" not in str(refused.value)

