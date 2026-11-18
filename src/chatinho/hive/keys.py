"""Keys: made at random, shown once, kept only as a hash."""


def make_key() -> str:
    """A new key: ``hive_`` and 48 random hex characters."""
    raise NotImplementedError


def hash_key(key: str) -> str:
    """What is stored for *key*: its SHA-256, in hex."""
    raise NotImplementedError
