"""
Keys and endpoints: where a secret lives, and which model it opens.

- :mod:`.sources` — key sources (``Env``, ``File``, ``Keyring``, …), read late
  and always as a ``Secret``;
- :mod:`.endpoint` — :class:`Endpoint`: a base URL, a model and a key source.

Standard library only.
"""

from .endpoint import Endpoint, profiles_file
from .sources import (
    Chain, Command, DotEnv, Env, File, Keyring, KeyLike, KeySource, KeyUnavailable, Literal,
    key, read_async, to_source,
)

__all__ = [
    "Chain", "Command", "DotEnv", "Endpoint", "Env", "File", "Keyring", "KeyLike", "KeySource",
    "KeyUnavailable", "Literal", "key", "profiles_file", "read_async", "to_source",
]
