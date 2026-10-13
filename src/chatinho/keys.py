"""Where a key or token lives, read when it is needed and always as a :class:`Secret`.

A key source says *where* a secret is — the environment, a ``.env`` file, a
private file, the OS keychain, a password manager's command — instead of
carrying the value. Every argument that takes a key or token accepts one, and a
plain string there still means the value itself::

    >>> from chatinho.keys import Chain, Env, File
    >>> key = Chain(Env("OPENAI_API_KEY"), File("~/.config/chatinho/openai.key"))

Reading may block (a keychain, a command), so :meth:`KeySource.read` is
synchronous and async code goes through :func:`read_async`. A source that cannot
yield a key raises :class:`KeyUnavailable`, whose message names the reference —
the variable, the file, the command — and never a value.

Reference strings (``env:NAME``, ``file:PATH``, …) are parsed only by
:func:`key`, which profile files use; in code, build the objects.
"""

import asyncio
import os
import pathlib
import shlex
import stat
import subprocess
import threading
from typing import Callable, Dict, List, Optional, Protocol, Sequence, Union, runtime_checkable

from .message import Secret


class KeyUnavailable(Exception):
    """A source could not yield its key; the message names the reference, never a value."""


@runtime_checkable
class KeySource(Protocol):
    """Anything that yields one secret when read."""

    def read(self) -> Secret:
        """Returns the secret, or raises :class:`KeyUnavailable`. May block."""
        ...


def _clean(value: str, where: str) -> Secret:
    """Strips surrounding whitespace and the trailing newline; an empty value is no key."""
    value = value.strip()
    if not value:
        raise KeyUnavailable("%s is empty" % where)
    return Secret(value)


class Literal:
    """A fixed value. What a plain string becomes wherever a key is accepted."""

    def __init__(self, value: Union[str, Secret]) -> None:
        self._value = value if isinstance(value, Secret) else Secret(value)

    def read(self) -> Secret:
        return _clean(self._value.reveal(), "the key given")

    def __repr__(self) -> str:
        return "Literal('***')"


class Env:
    """An environment variable, read anew each time, so a changed value is used."""

    def __init__(self, name: str) -> None:
        self.name = name

    def read(self) -> Secret:
        value = os.environ.get(self.name)
        if not value or not value.strip():
            raise KeyUnavailable("%s is not set" % self.name)
        return _clean(value, self.name)

    def __repr__(self) -> str:
        return "Env(%r)" % self.name


def _dotenv(text: str) -> Dict[str, str]:
    """``KEY=VALUE`` lines, with ``export``, ``#`` comments and surrounding quotes."""
    found : Dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        name, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        found[name.strip()] = value
    return found


class DotEnv:
    """One variable of a dotenv file, read anew each time.

    The file is not permission-checked: ``.env`` files usually sit, readable,
    with the project's other settings. For a dedicated key file, use :class:`File`.
    """

    def __init__(self, path: Union[str, os.PathLike] = ".env", name: str = "") -> None:
        self.path = pathlib.Path(path).expanduser()
        self.name = name

    def read(self) -> Secret:
        where = "%s in %s" % (self.name, self.path)
        try:
            text = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            raise KeyUnavailable("%s does not exist" % self.path) from None
        except OSError as exc:
            raise KeyUnavailable("%s cannot be read (%s)" % (self.path, type(exc).__name__)) from None
        value = _dotenv(text).get(self.name)
        if not value:
            raise KeyUnavailable("%s is not set" % where)
        return _clean(value, where)

    def __repr__(self) -> str:
        return "DotEnv(%r, %r)" % (str(self.path), self.name)


class File:
    """A whole file holding one key, read anew each time.

    On POSIX systems the file must be private: one its group or others can read
    or write is refused, since anyone who can read it has the key.
    """

    def __init__(self, path: Union[str, os.PathLike]) -> None:
        self.path = pathlib.Path(path).expanduser()

    def read(self) -> Secret:
        try:
            mode = self.path.stat().st_mode
        except FileNotFoundError:
            raise KeyUnavailable("%s does not exist" % self.path) from None
        except OSError as exc:
            raise KeyUnavailable("%s cannot be read (%s)" % (self.path, type(exc).__name__)) from None
        if os.name == "posix" and stat.S_IMODE(mode) & 0o077:
            raise KeyUnavailable("%s is readable by others; run  chmod 600 %s" % (self.path, self.path))
        try:
            text = self.path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise KeyUnavailable("%s cannot be read (%s)" % (self.path, type(exc).__name__)) from None
        return _clean(text, str(self.path))

    def __repr__(self) -> str:
        return "File(%r)" % str(self.path)


class _Once:
    """Reads through *fetch* the first time it succeeds, then keeps that value."""

    def __init__(self) -> None:
        self._lock  = threading.Lock()
        self._value : Optional[Secret] = None

    def get(self, fetch: Callable[[], Secret]) -> Secret:
        with self._lock:
            if self._value is None:
                self._value = fetch()
            return self._value


class Keyring:
    """An entry of the operating system's keychain, read once and kept.

    Needs ``pip install 'chatinho[keyring]'``; without it, reading says so.
    """

    def __init__(self, service: str, user: str) -> None:
        self.service = service
        self.user    = user
        self._once   = _Once()

    def read(self) -> Secret:
        return self._once.get(self._fetch)

    def _fetch(self) -> Secret:
        where = "keyring %s/%s" % (self.service, self.user)
        try:
            import keyring
        except ImportError:
            raise KeyUnavailable("%s: install  pip install 'chatinho[keyring]'" % where) from None
        try:
            value = keyring.get_password(self.service, self.user)
        except Exception as exc:                 # no usable backend, locked, …
            raise KeyUnavailable("%s: %s" % (where, type(exc).__name__)) from None
        if not value:
            raise KeyUnavailable("%s: no such entry" % where)
        return _clean(value, where)

    def __repr__(self) -> str:
        return "Keyring(%r, %r)" % (self.service, self.user)


class Command:
    """What a command prints, run once (without a shell) and kept.

    For password managers and encrypted files: ``Command("pass show api/openai")``,
    ``Command(["op", "read", "op://dev/openai/key"])``. Its output never appears
    in an error, since a failing command may have printed part of a secret.

    Its stdin is ``/dev/null``, so it never reads the chat's own input; password
    managers prompt through their own agent (pinentry, the 1Password app).
    """

    TIMEOUT = 30.0

    def __init__(self, argv: Union[str, Sequence[str]]) -> None:
        self.argv  = shlex.split(argv) if isinstance(argv, str) else list(argv)
        if not self.argv:
            raise ValueError("Command needs a program to run")
        self._once = _Once()

    def read(self) -> Secret:
        return self._once.get(self._fetch)

    def _fetch(self) -> Secret:
        where = "`%s`" % shlex.join(self.argv)
        try:
            done = subprocess.run(self.argv, stdin=subprocess.DEVNULL, capture_output=True,
                                  timeout=self.TIMEOUT, check=False)
        except FileNotFoundError:
            raise KeyUnavailable("%s: %s is not installed" % (where, self.argv[0])) from None
        except subprocess.TimeoutExpired:
            raise KeyUnavailable("%s timed out after %g s" % (where, self.TIMEOUT)) from None
        if done.returncode != 0:
            raise KeyUnavailable("%s exited %d" % (where, done.returncode))
        return _clean(done.stdout.decode("utf-8", "replace"), "%s output" % where)

    def __repr__(self) -> str:
        return "Command(%r)" % shlex.join(self.argv)


class Chain:
    """The first of several sources that yields a key, tried in order.

    Only a source with no key (:class:`KeyUnavailable`) passes to the next; when
    every one fails, the error lists each reason.
    """

    def __init__(self, *sources: "KeySource") -> None:
        if not sources:
            raise ValueError("Chain needs at least one source")
        self.sources = sources

    def read(self) -> Secret:
        reasons : List[str] = []
        for source in self.sources:
            try:
                return source.read()
            except KeyUnavailable as exc:
                reasons.append(str(exc))
        raise KeyUnavailable("; ".join(reasons))

    def __repr__(self) -> str:
        return "Chain(%s)" % ", ".join(repr(s) for s in self.sources)


class _Called:
    """A function returning the key, called on each read."""

    def __init__(self, fn: Callable[[], str]) -> None:
        self._fn = fn

    def read(self) -> Secret:
        value = self._fn()
        if isinstance(value, Secret):
            value = value.reveal()
        return _clean(value or "", "the key returned by %s" % getattr(self._fn, "__name__", "a function"))

    def __repr__(self) -> str:
        return "Called(%s)" % getattr(self._fn, "__name__", "?")


#: What every key or token argument accepts.
KeyLike = Union[str, Secret, Callable[[], str], KeySource]


def to_source(value: Optional[KeyLike]) -> Optional[KeySource]:
    """Normalises a key argument: a string or Secret is the value itself, never a reference."""
    if value is None:
        return None
    if isinstance(value, (str, Secret)):
        return Literal(value)
    if isinstance(value, KeySource):
        return value
    if callable(value):
        return _Called(value)
    raise TypeError("A key must be a string, a Secret, a key source or a function, not %s"
                    % type(value).__name__)


async def read_async(source: KeySource) -> Secret:
    """Reads *source* without blocking the event loop."""
    if isinstance(source, (Literal, Env)):
        return source.read()
    return await asyncio.get_running_loop().run_in_executor(None, source.read)


PREFIXES = ("env:", "dotenv:", "file:", "keyring:", "cmd:", "literal:")


def key(reference: str) -> KeySource:
    """Parses a reference string into a key source.

    ``env:NAME``, ``dotenv:PATH#NAME`` (``dotenv:#NAME`` for ``.env``),
    ``file:PATH``, ``keyring:SERVICE/USER``, ``cmd:COMMAND`` and ``literal:VALUE``.

    Raises:
        ValueError: Any other form; a typo is never taken as a key.
    """
    scheme, sep, rest = reference.partition(":")
    scheme = scheme.strip().lower()
    if sep and rest:
        if scheme == "env":
            return Env(rest.strip())
        if scheme == "dotenv" and "#" in rest:
            path, _, name = rest.rpartition("#")
            if name.strip():
                return DotEnv(path.strip() or ".env", name.strip())
        if scheme == "file":
            return File(rest.strip())
        if scheme == "keyring" and "/" in rest:
            service, _, user = rest.strip().partition("/")
            if service and user:
                return Keyring(service, user)
        if scheme == "cmd":
            return Command(rest)
        if scheme == "literal":
            return Literal(rest)
    # Name the prefix only when it looks like one: the string may be a key typed by mistake.
    shown = ("%s:…" % scheme if sep and scheme.isalpha() and len(scheme) <= 12
             else "a value without a known prefix")
    raise ValueError("Not a key reference (%s); use one of %s" % (shown, ", ".join(PREFIXES)))
