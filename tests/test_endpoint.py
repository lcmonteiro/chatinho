"""Endpoint: URL, model and key as one named profile.

See openspec/specs/endpoint-profiles.
"""

import os

import pytest

from chatinho.endpoint import Endpoint, profiles_file
from chatinho.keys import Env, KeyUnavailable, Literal

posix = pytest.mark.skipif(os.name != "posix", reason="POSIX permissions")

PROFILES = """
default = "nvidia"

[nvidia]
base_url = "https://integrate.api.nvidia.com/v1"
model    = "nvidia/big"
api_key  = "env:ORBE_OPENAI_API_KEY"

[local]
base_url = "http://localhost:11434/v1"
model    = "qwen"
api_key  = "literal:ollama"
"""


@pytest.fixture(autouse=True)
def clean(monkeypatch, tmp_path):
    """No profiles file and no relevant variables, unless a test adds them."""
    for name in ("CHATINHO_PROFILES", "CHATINHO_PROFILE", "CHATINHO_MODEL", "CHATINHO_BASE_URL",
                 "OPENAI_API_KEY", "OPENAI_BASE_URL", "ORBE_OPENAI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.chdir(tmp_path)


def profiles(monkeypatch, tmp_path, text: str = PROFILES, mode: int = 0o600):
    path = tmp_path / "profiles.toml"
    path.write_text(text)
    path.chmod(mode)
    monkeypatch.setenv("CHATINHO_PROFILES", str(path))
    return path


# === The value ====================================================================

def test_another_model_same_provider():
    base = Endpoint(base_url="https://example/v1", model="gpt-4o-mini", api_key=Literal("k"))
    copy = base.with_model("gpt-4o")
    assert (copy.model, copy.base_url, copy.api_key) == ("gpt-4o", "https://example/v1", base.api_key)
    assert base.model == "gpt-4o-mini"
    assert base.without_key().api_key is None


def test_never_shows_the_key():
    shown = repr(Endpoint(model="m", api_key=Literal("sk-1")))
    assert "sk-1" not in shown and "api_key" not in shown


def test_check_finds_a_missing_key_early():
    with pytest.raises(KeyUnavailable, match="OPENAI_API_KEY"):
        Endpoint(api_key=Env("OPENAI_API_KEY")).check()
    with pytest.raises(KeyUnavailable, match="no API key"):
        Endpoint().check()


def test_from_prefixed_variables(monkeypatch):
    monkeypatch.setenv("ORBE_OPENAI_API_KEY", "sk-orbe")
    monkeypatch.setenv("ORBE_OPENAI_BASE_URL", "https://x/v1")
    monkeypatch.setenv("ORBE_OPENAI_MODEL", "m-1")
    got = Endpoint.from_env("ORBE_OPENAI")
    assert (got.base_url, got.model, got.api_key.read().reveal()) == ("https://x/v1", "m-1", "sk-orbe")
    monkeypatch.setenv("ORBE_OPENAI_MODEL", "")
    monkeypatch.delenv("ORBE_OPENAI_BASE_URL")
    got = Endpoint.from_env("ORBE_OPENAI")
    assert (got.base_url, got.model) == (None, None)


# === Profiles =====================================================================

def test_a_profile_with_a_key_reference(monkeypatch, tmp_path):
    profiles(monkeypatch, tmp_path)
    monkeypatch.setenv("ORBE_OPENAI_API_KEY", "sk-nv")
    got = Endpoint.load("nvidia")
    assert got.base_url == "https://integrate.api.nvidia.com/v1"
    assert (got.model, got.profile) == ("nvidia/big", "nvidia")
    assert got.api_key.read().reveal() == "sk-nv"


def test_the_default_profile(monkeypatch, tmp_path):
    profiles(monkeypatch, tmp_path)
    assert Endpoint.load().profile == "nvidia"


def test_chosen_by_the_environment(monkeypatch, tmp_path):
    profiles(monkeypatch, tmp_path)
    monkeypatch.setenv("CHATINHO_PROFILE", "local")
    assert Endpoint.load().profile == "local"
    assert Endpoint.load("nvidia").profile == "nvidia"            # the argument wins


def test_field_overrides(monkeypatch, tmp_path):
    profiles(monkeypatch, tmp_path)
    monkeypatch.setenv("CHATINHO_MODEL", "small")
    monkeypatch.setenv("CHATINHO_BASE_URL", "http://other/v1")
    got = Endpoint.load("local")
    assert (got.model, got.base_url, got.api_key.read().reveal()) == ("small", "http://other/v1", "ollama")


def test_an_unknown_profile(monkeypatch, tmp_path):
    profiles(monkeypatch, tmp_path)
    with pytest.raises(ValueError) as refused:
        Endpoint.load("nvdia")
    assert "nvdia" in str(refused.value) and "local, nvidia" in str(refused.value)


def test_a_misspelled_field(monkeypatch, tmp_path):
    profiles(monkeypatch, tmp_path, '[x]\nmodle = "m"\n')
    with pytest.raises(ValueError, match="profile 'x' has an unknown field 'modle'"):
        Endpoint.load("x")


def test_a_bad_key_reference(monkeypatch, tmp_path):
    profiles(monkeypatch, tmp_path, '[x]\napi_key = "evn:K"\n')
    with pytest.raises(ValueError, match="api_key"):
        Endpoint.load("x")


@posix
def test_writable_by_others(monkeypatch, tmp_path):
    path = profiles(monkeypatch, tmp_path, mode=0o666)
    with pytest.raises(ValueError, match=str(path)):
        Endpoint.load("local")


def test_the_projects_file_wins(monkeypatch, tmp_path):
    user = tmp_path / "config" / "chatinho" / "profiles.toml"
    user.parent.mkdir(parents=True)
    user.write_text('[only_user]\nmodel = "u"\n')
    user.chmod(0o600)
    assert profiles_file() == user
    project = tmp_path / ".chatinho.toml"
    project.write_text('[only_project]\nmodel = "p"\n')
    project.chmod(0o600)
    assert profiles_file().resolve() == project.resolve()
    assert Endpoint.load("only_project").model == "p"
    with pytest.raises(ValueError, match="only_project"):
        Endpoint.load("only_user")


def test_a_profile_but_no_file(monkeypatch):
    monkeypatch.setenv("CHATINHO_PROFILE", "nvidia")
    with pytest.raises(ValueError) as refused:
        Endpoint.load()
    assert "nvidia" in str(refused.value) and "profiles.toml" in str(refused.value)


def test_no_profiles_file(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://compat/v1")
    monkeypatch.setenv("CHATINHO_MODEL", "m")
    got = Endpoint.load()
    assert (got.base_url, got.model, got.profile) == ("https://compat/v1", "m", None)
    assert got.api_key.read().reveal() == "sk-env"


def test_a_plain_string_key_is_the_value(monkeypatch):
    monkeypatch.setenv("X", "from-env")
    endpoint = Endpoint(api_key="env:X")
    assert isinstance(endpoint.api_key, Literal) and endpoint.key.read().reveal() == "env:X"
    assert Endpoint(api_key=lambda: "sk-fn").key.read().reveal() == "sk-fn"
    assert Endpoint().key is None
