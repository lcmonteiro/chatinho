"""An OpenAI-compatible endpoint, its default model and its key, as one named profile.

:class:`Endpoint` bundles the three, so the same program can switch provider or
model without code changes::

    assistant = OpenAIConnector(name="assistant", endpoint=Endpoint.load())

    $ CHATINHO_PROFILE=local python app.py

Profiles live in a TOML file; the key is only ever a reference in it::

    default = "nvidia"

    [nvidia]
    base_url = "https://integrate.api.nvidia.com/v1"
    model    = "nvidia/nemotron-3-super-120b-a12b"
    api_key  = "env:ORBE_OPENAI_API_KEY"

The file is the first that exists of ``$CHATINHO_PROFILES``, ``./.chatinho.toml``
and ``chatinho/profiles.toml`` under ``$XDG_CONFIG_HOME`` (``~/.config``).
"""

import dataclasses
import os
import pathlib
import stat
import tomllib
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .keys import Env, KeySource, KeyUnavailable, key

#: The fields a profile may set.
FIELDS = ("base_url", "model", "api_key")


@dataclass(frozen=True)
class Endpoint:
    """Where to ask, which model, and with which key.

    Attributes:
        base_url: An OpenAI-compatible endpoint; None for OpenAI itself.
        model: The model to ask; None leaves the choice to whoever uses it.
        api_key: Where the key is read from; None for an endpoint without one.
        profile: The profile it was loaded from, if any.
    """

    base_url : Optional[str] = None
    model    : Optional[str] = None
    api_key  : Optional[KeySource] = dataclasses.field(default=None, repr=False)
    profile  : Optional[str] = None

    def with_model(self, model: str) -> "Endpoint":
        """The same endpoint and key, with another model."""
        return dataclasses.replace(self, model=model)

    def without_key(self) -> "Endpoint":
        """The same endpoint and model, with no key: for a server that answers with lent keys."""
        return dataclasses.replace(self, api_key=None)

    def check(self) -> None:
        """Reads the key once, so a program can stop before it starts its interface.

        It does not contact the endpoint.

        Raises:
            KeyUnavailable: There is no key source, or it cannot yield a key.
        """
        if self.api_key is None:
            raise KeyUnavailable("%s has no API key configured" % self._called())
        self.api_key.read()

    def _called(self) -> str:
        return "profile %r" % self.profile if self.profile else "the endpoint"

    # === Building one ===============================================================

    @classmethod
    def from_env(cls, prefix: str = "OPENAI") -> "Endpoint":
        """From ``<prefix>_API_KEY`` (read when needed), ``<prefix>_BASE_URL`` and ``<prefix>_MODEL``."""
        return cls(base_url = os.environ.get("%s_BASE_URL" % prefix) or None,
                   model    = os.environ.get("%s_MODEL" % prefix) or None,
                   api_key  = Env("%s_API_KEY" % prefix))

    @classmethod
    def load(cls, profile: Optional[str] = None) -> "Endpoint":
        """A profile from the profiles file, or the ``OPENAI_*`` environment without one.

        The profile is *profile*, else ``$CHATINHO_PROFILE``, else the file's
        ``default``. ``$CHATINHO_MODEL`` and ``$CHATINHO_BASE_URL`` then replace
        its model and URL. With no profile chosen or no profiles file, the key
        is read from ``OPENAI_API_KEY``, the URL from ``OPENAI_BASE_URL`` and the
        model from ``CHATINHO_MODEL``.

        Raises:
            ValueError: The file is malformed, writable by others, or lacks the profile.
        """
        path   = profiles_file()
        table  = _read(path) if path is not None else {}
        chosen = profile or os.environ.get("CHATINHO_PROFILE") or table.get("default")
        if chosen is not None and not isinstance(chosen, str):
            raise ValueError("%s: default must be a profile name" % path)
        if not chosen:
            found = dataclasses.replace(cls.from_env("OPENAI"), model=None)
        elif path is None:
            raise ValueError("Profile %r asked for, but there is no profiles file (%s)"
                             % (chosen, ", ".join(str(p) for p in _candidates())))
        else:
            found = _profile(path, table, chosen)
        return dataclasses.replace(
            found,
            model    = os.environ.get("CHATINHO_MODEL") or found.model,
            base_url = os.environ.get("CHATINHO_BASE_URL") or found.base_url,
        )


# === The profiles file ============================================================

def _candidates() -> List[pathlib.Path]:
    """Where a profiles file may be, in the order they are tried."""
    config = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    given  = os.environ.get("CHATINHO_PROFILES")
    found  = [pathlib.Path(given).expanduser()] if given else []
    return found + [pathlib.Path(".chatinho.toml"), pathlib.Path(config) / "chatinho" / "profiles.toml"]


def profiles_file() -> Optional[pathlib.Path]:
    """The profiles file in use: the first of the candidates that exists, or None."""
    return next((path for path in _candidates() if path.is_file()), None)


def _read(path: pathlib.Path) -> Dict[str, Any]:
    if os.name == "posix" and stat.S_IMODE(path.stat().st_mode) & 0o022:
        raise ValueError("%s is writable by others, and a profile may run a command; "
                         "run  chmod go-w %s" % (path, path))
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        raise ValueError("%s is not valid TOML: %s" % (path, exc)) from None


def _profile(path: pathlib.Path, table: Dict[str, Any], name: str) -> Endpoint:
    profiles = {k: v for k, v in table.items() if isinstance(v, dict)}
    if name not in profiles:
        raise ValueError("No profile %r in %s (have: %s)"
                         % (name, path, ", ".join(sorted(profiles)) or "none"))
    fields = profiles[name]
    for field, value in fields.items():
        if field not in FIELDS:
            raise ValueError("%s: profile %r has an unknown field %r (allowed: %s)"
                             % (path, name, field, ", ".join(FIELDS)))
        if not isinstance(value, str):
            raise ValueError("%s: profile %r: %s must be a string" % (path, name, field))
    try:
        api_key = key(fields["api_key"]) if "api_key" in fields else None
    except ValueError as exc:
        raise ValueError("%s: profile %r: api_key: %s" % (path, name, exc)) from None
    return Endpoint(base_url=fields.get("base_url") or None, model=fields.get("model") or None,
                    api_key=api_key, profile=name)
