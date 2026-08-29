"""Tests for DatabaseBackend — the only real persistence adapter.

It had never stored a row: ``ChatData.id`` was a String primary key with no
default that ``save()`` never set, so every INSERT failed the NOT NULL
constraint, the broad ``except`` swallowed it and ``save()`` returned False.
Nothing noticed because nothing tested it. These run against SQLite, in
memory and on disk.
"""

import pytest

from chatinho import DatabaseBackend
from chatinho.backends.database import ChatData


@pytest.fixture
def backend():
    """An initialized in-memory backend."""
    backend = DatabaseBackend("sqlite:///:memory:")
    backend.initialize()
    return backend


# === The regression =============================================================


def test_save_actually_stores_a_row(backend):
    """The bug: save() reported False and stored nothing."""
    assert backend.save("k", {"a": 1}) is True
    session = backend._get_session()
    try:
        assert session.query(ChatData).filter(ChatData.key == "k").count() == 1
    finally:
        session.close()


def test_save_does_not_swallow_an_integrity_error(backend):
    """A round trip proves the INSERT really committed, not just returned True."""
    backend.save("k", "value")
    assert backend.load("k") == "value"


# === Round trips by type ========================================================


@pytest.mark.parametrize(
    "value",
    [
        {"message": "Hello", "n": 1},
        ["a", "b", "c"],
        "plain string",
        42,
        3.5,
        True,
    ],
)
def test_round_trip_preserves_the_value(backend, value):
    assert backend.save("k", value) is True
    assert backend.load("k") == value


def test_round_trip_preserves_non_ascii(backend):
    backend.save("k", {"texto": "olá, ção — ✓"})
    assert backend.load("k") == {"texto": "olá, ção — ✓"}


# === Overwrite, missing keys, delete ============================================


def test_saving_the_same_key_twice_overwrites(backend):
    backend.save("k", "primeiro")
    assert backend.save("k", "segundo") is True
    assert backend.load("k") == "segundo"
    session = backend._get_session()
    try:
        assert session.query(ChatData).count() == 1
    finally:
        session.close()


def test_overwrite_can_change_the_stored_type(backend):
    backend.save("k", "uma string")
    backend.save("k", {"agora": "json"})
    assert backend.load("k") == {"agora": "json"}


def test_load_returns_none_for_an_unknown_key(backend):
    assert backend.load("nao-existe") is None


def test_delete_removes_the_row(backend):
    backend.save("k", "value")
    assert backend.delete("k") is True
    assert backend.load("k") is None


def test_delete_returns_false_for_an_unknown_key(backend):
    assert backend.delete("nao-existe") is False


def test_keys_do_not_collide(backend):
    backend.save("a", 1)
    backend.save("b", 2)
    assert (backend.load("a"), backend.load("b")) == (1, 2)
    backend.delete("a")
    assert backend.load("b") == 2


# === Lifecycle ==================================================================


def test_using_the_backend_before_initialize_raises():
    backend = DatabaseBackend("sqlite:///:memory:")
    for call in (
        lambda: backend.save("k", 1),
        lambda: backend.load("k"),
        lambda: backend.delete("k"),
    ):
        with pytest.raises(RuntimeError):
            call()


def test_data_survives_on_a_real_file(tmp_path):
    """Not an in-memory artefact: a second backend reads the first one's rows."""
    db = tmp_path / "chat.db"
    writer = DatabaseBackend(f"sqlite:///{db}")
    writer.initialize()
    assert writer.save("k", {"a": 1}) is True

    reader = DatabaseBackend(f"sqlite:///{db}")
    reader.initialize()
    assert reader.load("k") == {"a": 1}


def test_an_absolute_sqlite_path_is_honoured(tmp_path):
    """The URL is handed to SQLAlchemy untouched, so absolute paths work."""
    db = tmp_path / "nested" / "chat.db"
    db.parent.mkdir()
    backend = DatabaseBackend(f"sqlite:////{db.relative_to('/')}")
    backend.initialize()
    assert backend.save("k", "value") is True
    assert db.exists()
