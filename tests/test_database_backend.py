"""Tests for the message archive — the older tier of the conversation.

The backend is not a key-value store. It keeps messages, the session recalls a
window at startup, and every method is a coroutine that does its SQLAlchemy
work off the event loop.
"""

from datetime import datetime, timedelta

import pytest

from chatinho import LOCAL, ChatMessage, ChatSession, DatabaseBackend
from conftest import Driver


def message(mid: str, text: str, at: datetime, frm: int = LOCAL) -> ChatMessage:
    """Builds one message stamped at a given moment."""
    return ChatMessage(id=mid, text=text, frm=frm, timestamp=at)


async def heard(archive, *messages) -> None:
    """Lets the archive hear each message, the way the session would."""
    for msg in messages:
        await archive.overhear(msg)


@pytest.fixture
async def archive():
    """A started, on-disk-free archive."""
    store = DatabaseBackend("sqlite:///:memory:")
    store.initialize()
    yield store
    store.shutdown()


# === The archive itself =========================================================


async def test_what_goes_in_comes_back_out(archive):
    now = datetime.now()
    await heard(archive, message("msg-1", "ola", now), message("msg-2", "adeus", now))
    assert [m.text for m in await archive.load()] == ["ola", "adeus"]


async def test_a_message_keeps_its_address_and_its_thread(archive):
    now = datetime.now()
    await heard(archive, 
        ChatMessage(id="msg-1", text="que tempo?", frm=LOCAL, to=1, timestamp=now),
        ChatMessage(id="msg-2", text="sol", frm=1, to=LOCAL, reply_to="msg-1",
                    timestamp=now + timedelta(seconds=1)),
    )
    question, answer = await archive.load()
    assert (question.frm, question.to) == (LOCAL, 1)
    assert (answer.frm, answer.to, answer.reply_to) == (1, LOCAL, "msg-1")


async def test_hearing_the_same_message_twice_is_not_two_rows(archive):
    """The message id is the primary key, so a re-archive replaces."""
    now = datetime.now()
    await heard(archive, message("msg-1", "primeira", now))
    await heard(archive, message("msg-1", "corrigida", now))
    recalled = await archive.load()
    assert [(m.id, m.text) for m in recalled] == [("msg-1", "corrigida")]


async def test_load_takes_the_tail_oldest_first(archive):
    base = datetime.now()
    await heard(archive, *(message("msg-%d" % n, "m%d" % n, base + timedelta(seconds=n))
                           for n in range(5)))
    assert [m.text for m in await archive.load(limit=2)] == ["m3", "m4"]


async def test_load_narrows_by_time(archive):
    base = datetime.now()
    await heard(archive, *(message("msg-%d" % n, "m%d" % n, base + timedelta(seconds=n))
                           for n in range(5)))
    cut = base + timedelta(seconds=3)
    assert [m.text for m in await archive.load(since=cut)] == ["m3", "m4"]


async def test_forget_drops_only_what_is_older(archive):
    base = datetime.now()
    await heard(archive, *(message("msg-%d" % n, "m%d" % n, base + timedelta(seconds=n))
                           for n in range(5)))
    assert await archive.forget(before=base + timedelta(seconds=3)) == 3
    assert [m.text for m in await archive.load()] == ["m3", "m4"]


async def test_forget_without_a_cut_forgets_everything(archive):
    await heard(archive, message("msg-1", "ola", datetime.now()))
    assert await archive.forget() == 1
    assert await archive.load() == []


async def test_using_it_before_initialize_says_so():
    store = DatabaseBackend("sqlite:///:memory:")
    with pytest.raises(RuntimeError, match="not initialized"):
        await heard(store, message("msg-1", "ola", datetime.now()))


async def test_shutdown_disposes_of_the_engine(archive):
    assert archive.engine is not None
    archive.shutdown()
    assert archive.engine is None


# === Wired to a session =========================================================


async def test_a_conversation_survives_the_session_that_had_it(tmp_path):
    """The whole point: close the chat, open another, and the context is there."""
    store = DatabaseBackend("sqlite:///%s" % (tmp_path / "chat.db"))

    first = ChatSession(backend=store)
    view = Driver()
    first.attach(view, at=LOCAL)
    await first.start()
    await view.say("lembra-te disto")
    await first.close()

    second = ChatSession(backend=store)
    again = Driver()
    second.attach(again, at=LOCAL)
    await second.start()
    assert [m.text for m in again.context()] == ["lembra-te disto"]
    await second.close()


async def test_a_session_without_a_backend_simply_has_no_older_tier():
    session = ChatSession()
    view = Driver()
    session.attach(view, at=LOCAL)
    await session.start()
    await view.say("só em memória")
    assert [m.text for m in view.context()] == ["só em memória"]
    assert await session.forget() == 0
    await session.close()


async def test_load_is_bounded_by_what_the_session_asks_for(tmp_path):
    """The window is stated, not hidden: older than `recall` is out of reach."""
    store = DatabaseBackend("sqlite:///%s" % (tmp_path / "chat.db"))
    first = ChatSession(backend=store)
    view = Driver()
    first.attach(view, at=LOCAL)
    await first.start()
    for n in range(5):
        await view.say("m%d" % n)
    await first.close()

    second = ChatSession(backend=store, recall=2)
    again = Driver()
    second.attach(again, at=LOCAL)
    await second.start()
    assert [m.text for m in again.context()] == ["m3", "m4"]
    await second.close()
