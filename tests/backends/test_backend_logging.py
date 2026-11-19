"""
Tests for what the archives log: what they load, forget, keep, link and send, by counts and ids only.
"""

import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import Callable, List

import pytest

from chatinho import Attachment, ChatMessage, DatabaseBackend, HiveBackend, HookTrace, LOCAL, MessageID
from chatinho import Trace, TraceState, connector, require
from conftest import driven
from fakes.hive import make_hive, served


@pytest.fixture(autouse=True)
def everything(caplog):
    caplog.set_level(logging.DEBUG, logger="chatinho")
    return caplog


def having(caplog, *words: str) -> List[str]:
    return [r.getMessage() for r in caplog.records
            if r.name.startswith("chatinho") and all(w in r.getMessage() for w in words)]


async def until(check: Callable[[], bool], wait: float = 5.0) -> None:
    deadline = asyncio.get_running_loop().time() + wait
    while not check():
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError("timed out waiting")
        await asyncio.sleep(0.05)


@pytest.fixture
def hive(tmp_path):
    hive = make_hive(tmp_path, "team")
    with served(hive.db) as server:
        hive.url = server.url                     # type: ignore[attr-defined]
        yield hive


@connector("rastro")
@require(HookTrace)
class Tracer:
    trace : Trace


# @ac AC-BACK-014.1
async def test_the_database_archive_logs_what_it_loads_and_forgets(caplog):
    archive = DatabaseBackend("sqlite:///:memory:")
    archive.initialize()
    try:
        now = datetime.now()
        for n in range(3):
            await archive.listen(ChatMessage(id=MessageID.new(), text="m%d" % n, frm=LOCAL,
                                             timestamp=now + timedelta(seconds=n)))
        loaded = await archive.load()
        gone   = await archive.forget(before=now + timedelta(seconds=2))
    finally:
        archive.shutdown()
    assert len(loaded) == 3 and gone == 2
    assert having(caplog, "loaded", "3")
    assert having(caplog, "forgot", "2")


# @ac AC-BACK-014.2
async def test_a_batch_sent_to_the_hive_is_logged_with_its_counts(hive, caplog):
    session, view = await driven(backend=HiveBackend(hive.url, hive.keys["team"]),
                                 connectors=[Tracer()])
    first = await view.say("one")
    await view.say("two")
    tracer = next(p for p in view.peers().values() if getattr(p, "name", "") == "rastro")
    await tracer.trace(first, TraceState.DONE, "a step")
    await until(lambda: any("trace" in line for line in having(caplog, "sent")))
    await session.close()
    lines = having(caplog, "sent")
    assert any("trace" in line for line in lines)
    assert all("waiting" in line for line in lines)
    assert sum(int(n) for line in lines for n in re.findall(r"(\d+) messages?\b", line)) >= 2


# @ac AC-BACK-014.3
async def test_neither_archive_logs_what_was_said_or_the_key(hive, tmp_path, caplog):
    text = "DISTINCT-said-zebra"
    data = b"DISTINCT-attached-zebra"
    for backend in (HiveBackend(hive.url, hive.keys["team"]),
                    DatabaseBackend("sqlite:///%s" % (tmp_path / "chat.db"))):
        session, view = await driven(backend=backend)
        await view.say(text, attachments=[Attachment("note.txt", "text/plain", data)])
        await asyncio.sleep(0.3)
        await session.close()
        session, view = await driven(backend=backend.__class__(*((hive.url, hive.keys["team"])
                                     if isinstance(backend, HiveBackend)
                                     else ("sqlite:///%s" % (tmp_path / "chat.db"),))))
        await session.forget()
        await session.close()
    every = "\n".join(r.getMessage() for r in caplog.records)
    assert text not in every
    assert data.decode() not in every
    assert hive.keys["team"] not in every
    assert having(caplog, "kept")
    assert having(caplog, "loaded")
    assert having(caplog, "forgot")


# @ac AC-BACK-014.3
def test_the_database_archive_never_logs_its_password(tmp_path, caplog):
    """The archive's URL is logged when it opens, with the password masked (found in review, R1)."""
    # SQLite takes no credentials and refuses the URL, but only after it was logged: what matters here.
    archive = DatabaseBackend("sqlite://reader:PASSWORD-zebra@/%s" % (tmp_path / "chat.db"))
    with pytest.raises(Exception, match="SQLite URL"):
        archive.initialize()
    every = "\n".join(r.getMessage() for r in caplog.records)
    assert "PASSWORD-zebra" not in every
    assert having(caplog, "Opening the message archive", "reader")
