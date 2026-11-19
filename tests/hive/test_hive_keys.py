"""
Tests for a hive's chats and keys: a chat is a name and a key, made by a command and shown once.

See src/chatinho/hive/docs/spec.md.
"""

import contextlib
import io
import sqlite3

from fastapi.testclient import TestClient

from chatinho.hive import create_app
from chatinho.hive.cli import main
from chatinho.hive.keys import hash_key
from chatinho.support.parts.hive import KEY_HEADER
from fakes.hive import command, key_in, make_hive, message, wire_messages


def run(*argv: str):
    """Runs ``chatinho-hive`` and returns its status and output, whatever the status."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        status = main(list(argv))
    return status, out.getvalue()


def everything_stored(db: str) -> str:
    """Every value in every table, as one string."""
    with sqlite3.connect(db.removeprefix("sqlite:///")) as conn:
        tables = [t for (t,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        return repr([conn.execute("SELECT * FROM %s" % t).fetchall() for t in tables])


# @ac AC-HIVE-001.1
def test_adding_a_chat_prints_a_key_and_stores_only_its_hash(tmp_path):
    db  = "sqlite:///%s" % (tmp_path / "hive.db")
    key = key_in(command("chat", "add", "team", "--db", db))
    assert len(key) > 32
    stored = everything_stored(db)
    assert "team" in stored
    assert key not in stored
    assert hash_key(key) in stored


# @ac AC-HIVE-001.1
def test_the_printed_key_is_accepted_for_its_chat(tmp_path):
    hive = make_hive(tmp_path, "team")
    with TestClient(create_app(hive.db)) as client:
        answer = client.get("/api/messages", headers={KEY_HEADER: hive.keys["team"]})
    assert answer.status_code == 200


# @ac AC-HIVE-001.2
def test_a_name_taken_is_refused_and_the_first_key_still_works(tmp_path):
    hive           = make_hive(tmp_path, "team")
    status, output = run("chat", "add", "team", "--db", hive.db)
    assert status != 0
    assert "taken" in output
    with TestClient(create_app(hive.db)) as client:
        assert client.get("/api/messages", headers={KEY_HEADER: hive.keys["team"]}).status_code == 200


# @ac AC-HIVE-001.3
def test_a_bad_name_says_which_characters_a_name_may_have(tmp_path):
    db = "sqlite:///%s" % (tmp_path / "hive.db")
    for name in ("Team One", "", "x" * 65, "équipe"):
        status, output = run("chat", "add", name, "--db", db)
        assert status != 0, name
        assert "a-z" in output, name


# @ac AC-HIVE-001.4
def test_listing_shows_names_and_never_a_key_or_hash(tmp_path):
    hive    = make_hive(tmp_path, "team", "solo")
    listing = command("chat", "list", "--db", hive.db)
    assert "team" in listing and "solo" in listing
    for key in hive.keys.values():
        assert key not in listing
        assert hash_key(key) not in listing


# @ac AC-HIVE-001.5
def test_removing_a_chat_removes_everything_and_refuses_its_key(tmp_path):
    hive    = make_hive(tmp_path, "team")
    headers = {KEY_HEADER: hive.keys["team"]}
    msg     = message(1)
    with TestClient(create_app(hive.db)) as client:
        posted = client.post("/api/messages", json={"messages": wire_messages(msg)}, headers=headers)
        assert posted.status_code == 200
        client.put("/api/messages/%s/attachments/notes.md" % msg.id, content=b"# notes",
                   headers={**headers, "Content-Type": "text/markdown"})
    command("chat", "remove", "team", "--db", hive.db)
    assert str(msg.id) not in everything_stored(hive.db)
    assert "team" not in command("chat", "list", "--db", hive.db)
    with TestClient(create_app(hive.db)) as client:
        assert client.get("/api/messages", headers=headers).status_code == 401


# @ac AC-HIVE-002.1
def test_an_admin_key_reads_the_chat_list(tmp_path):
    hive = make_hive(tmp_path, "team")
    assert hive.admin not in everything_stored(hive.db)
    with TestClient(create_app(hive.db)) as client:
        answer = client.get("/api/chats", headers={KEY_HEADER: hive.admin})
    assert answer.status_code == 200
    assert [c["name"] for c in answer.json()["chats"]] == ["team"]


# @ac AC-HIVE-002.2
def test_an_admin_cannot_write(tmp_path):
    hive = make_hive(tmp_path, "team")
    with TestClient(create_app(hive.db)) as client:
        answer = client.post("/api/messages", json={"messages": wire_messages(message(1))},
                             headers={KEY_HEADER: hive.admin})
    assert answer.status_code == 403
