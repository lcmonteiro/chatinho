"""Keys: made at random, shown once, kept only as a hash."""

import hashlib
import secrets

#: What every key starts with, so one pasted into the wrong place is recognisable.
PREFIX : str = "hive_"


# @req REQ-HIVE-001, REQ-HIVE-002
def make_key() -> str:
    """A new key: ``hive_`` and 48 random hex characters."""
    return PREFIX + secrets.token_hex(24)


# @req REQ-HIVE-001, REQ-HIVE-002
def hash_key(key: str) -> str:
    """
    What is stored for *key*: its SHA-256, in hex.

    A key is 192 random bits, so a plain hash is enough: there is nothing to
    guess that a slow hash would protect, and the hash can be the index a
    request's key is looked up by.
    """
    return hashlib.sha256(key.encode("utf-8")).hexdigest()
