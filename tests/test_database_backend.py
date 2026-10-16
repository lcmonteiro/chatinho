"""Tests for the message archive — the older tier of the conversation.

The backend is not a key-value store. It keeps messages, the session recalls a
window at startup, and every method is a coroutine that does its SQLAlchemy
work off the event loop.
"""

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import unquote, urlparse

import pytest

from chatinho import (
    LOCAL, Attachment, ChatMessage, ChatSession, DatabaseBackend, HookAnswer, MessageID, Query, Reply,
    connector, require,
)
from conftest import Driver


mid = MessageID.parse


def message(msg_id: MessageID, text: str, at: datetime, frm: int = LOCAL) -> ChatMessage:
    """Builds one message stamped at a given moment."""
    return ChatMessage(id=msg_id, text=text, frm=frm, timestamp=at)


async def heard(archive, *messages) -> None:
    """Lets the archive hear each message, the way the session would."""
    for msg in messages:
        await archive.listen(msg)


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
    await heard(archive, message(mid("msg-1"), "ola", now), message(mid("msg-2"), "adeus", now))
    assert [m.text for m in await archive.load()] == ["ola", "adeus"]


async def test_a_message_keeps_its_address_and_its_thread(archive):
    now = datetime.now()
    await heard(archive, 
        ChatMessage(id=mid("msg-1"), text="que tempo?", frm=LOCAL, to=1, timestamp=now),
        ChatMessage(id=mid("msg-2"), text="sol", frm=1, to=LOCAL, reply_to=mid("msg-1"),
                    timestamp=now + timedelta(seconds=1)),
    )
    question, answer = await archive.load()
    assert (question.frm, question.to) == (LOCAL, 1)
    assert (answer.frm, answer.to, answer.reply_to) == (1, LOCAL, mid("msg-1"))


async def test_hearing_the_same_message_twice_is_not_two_rows(archive):
    """The message id is the primary key, so a re-archive replaces."""
    now = datetime.now()
    await heard(archive, message(mid("msg-1"), "primeira", now))
    await heard(archive, message(mid("msg-1"), "corrigida", now))
    recalled = await archive.load()
    assert [(m.id, m.text) for m in recalled] == [(mid("msg-1"), "corrigida")]


async def test_load_takes_the_tail_oldest_first(archive):
    base = datetime.now()
    await heard(archive, *(message(mid("msg-%d" % n), "m%d" % n, base + timedelta(seconds=n))
                           for n in range(5)))
    assert [m.text for m in await archive.load(limit=2)] == ["m3", "m4"]


async def test_load_narrows_by_time(archive):
    base = datetime.now()
    await heard(archive, *(message(mid("msg-%d" % n), "m%d" % n, base + timedelta(seconds=n))
                           for n in range(5)))
    cut = base + timedelta(seconds=3)
    assert [m.text for m in await archive.load(since=cut)] == ["m3", "m4"]


async def test_forget_drops_only_what_is_older(archive):
    base = datetime.now()
    await heard(archive, *(message(mid("msg-%d" % n), "m%d" % n, base + timedelta(seconds=n))
                           for n in range(5)))
    assert await archive.forget(before=base + timedelta(seconds=3)) == 3
    assert [m.text for m in await archive.load()] == ["m3", "m4"]


async def test_forget_without_a_cut_forgets_everything(archive):
    await heard(archive, message(mid("msg-1"), "ola", datetime.now()))
    assert await archive.forget() == 1
    assert await archive.load() == []


async def test_using_it_before_initialize_says_so():
    store = DatabaseBackend("sqlite:///:memory:")
    with pytest.raises(RuntimeError, match="not initialized"):
        await heard(store, message(mid("msg-1"), "ola", datetime.now()))


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
    first.add_connector(view, at=LOCAL)
    await first.start()
    await view.say("lembra-te disto")
    await first.close()

    second = ChatSession(backend=store)
    again = Driver()
    second.add_connector(again, at=LOCAL)
    await second.start()
    assert [m.text for m in again.context()] == ["lembra-te disto"]
    await second.close()


async def test_concurrent_messages_are_all_archived_in_order(tmp_path):
    """The session hands the backend messages concurrently; none is lost or reordered."""
    store = DatabaseBackend("sqlite:///%s" % (tmp_path / "chat.db"))
    first = ChatSession(backend=store)
    view  = Driver()
    first.add_connector(view, at=LOCAL)
    await first.start()
    for n in range(50):
        await view.say("message %02d" % n)
    await first.close()

    second = ChatSession(backend=store, recall=100)
    again  = Driver()
    second.add_connector(again, at=LOCAL)
    await second.start()
    assert [m.text for m in again.context()] == ["message %02d" % n for n in range(50)]
    await second.close()


async def test_an_in_memory_archive_takes_concurrent_writes(archive):
    """One shared connection, fifty writers at once: every row arrives."""
    start    = datetime(2026, 1, 1)
    messages = [message(MessageID.new(), "m%02d" % n, start + timedelta(seconds=n)) for n in range(50)]
    await asyncio.gather(*(archive.listen(m) for m in messages))
    assert [m.text for m in await archive.load()] == ["m%02d" % n for n in range(50)]


async def test_a_session_without_a_backend_simply_has_no_older_tier():
    session = ChatSession()
    view = Driver()
    session.add_connector(view, at=LOCAL)
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
    first.add_connector(view, at=LOCAL)
    await first.start()
    for n in range(5):
        await view.say("m%d" % n)
    await first.close()

    second = ChatSession(backend=store, recall=2)
    again = Driver()
    second.add_connector(again, at=LOCAL)
    await second.start()
    assert [m.text for m in again.context()] == ["m3", "m4"]
    await second.close()


# === What messages carry ========================================================


def page(name: str = "revenue.html", data: bytes = b"<p>up 12%</p>") -> Attachment:
    return Attachment(name, "text/html", data)


def content(link: str) -> bytes:
    """What a file:// link points at."""
    assert link.startswith("file://")
    return Path(unquote(urlparse(link).path)).read_bytes()


async def test_a_kept_attachment_links_to_a_file_with_its_data(archive):
    await archive.keep(mid("msg-1"), [page()])
    link = await archive.link(mid("msg-1"), "revenue.html")
    assert link is not None and content(link) == b"<p>up 12%</p>"


async def test_a_name_never_kept_has_no_link(archive):
    await archive.keep(mid("msg-1"), [page()])
    assert await archive.link(mid("msg-1"), "other.html") is None
    assert await archive.link(mid("msg-2"), "revenue.html") is None


async def test_keeping_the_same_attachment_twice_is_one_row(archive):
    from chatinho.backends.database import ArchivedAttachment

    await archive.keep(mid("msg-1"), [page()])
    await archive.keep(mid("msg-1"), [page()])
    with archive._session() as session:
        assert session.query(ArchivedAttachment).count() == 1


async def test_a_name_that_is_not_a_file_name_still_links(archive):
    await archive.keep(mid("msg-1"), [page("my report/v2.html")])
    link = await archive.link(mid("msg-1"), "my report/v2.html")
    assert link is not None and content(link) == b"<p>up 12%</p>"


@pytest.mark.parametrize("name", ["..", "."])
async def test_a_dot_name_links_to_a_file_not_a_folder(archive, name):
    await archive.keep(mid("msg-1"), [page("revenue.html"), page(name, b"dots")])
    await archive.link(mid("msg-1"), "revenue.html")          # the folders exist first
    link = await archive.link(mid("msg-1"), name)
    assert link is not None and content(link) == b"dots"


async def test_shutdown_removes_the_files_it_wrote():
    store = DatabaseBackend("sqlite:///:memory:")
    store.initialize()
    await store.keep(mid("msg-1"), [page()])
    link = await store.link(mid("msg-1"), "revenue.html")
    assert link is not None
    written = Path(unquote(urlparse(link).path))
    assert written.exists()
    store.shutdown()
    assert not written.exists()


async def test_forget_drops_what_the_forgotten_messages_carried(archive):
    now = datetime.now()
    await heard(archive, message(mid("msg-1"), "old", now - timedelta(hours=2)),
                message(mid("msg-2"), "new", now))
    await archive.keep(mid("msg-1"), [page()])
    await archive.keep(mid("msg-2"), [page()])
    await archive.forget(before=now - timedelta(hours=1))
    assert await archive.link(mid("msg-1"), "revenue.html") is None
    assert await archive.link(mid("msg-2"), "revenue.html") is not None


async def test_forgetting_everything_drops_every_attachment(archive):
    await heard(archive, message(mid("msg-1"), "old", datetime.now()))
    await archive.keep(mid("msg-1"), [page()])
    await archive.keep(mid("msg-9"), [page()])             # kept, even with no message heard
    await archive.forget()
    assert await archive.link(mid("msg-1"), "revenue.html") is None
    assert await archive.link(mid("msg-9"), "revenue.html") is None


async def test_an_attachment_outlives_the_session_that_said_it(tmp_path):
    """Close the chat, open another on the same file, and the link still opens."""
    store = DatabaseBackend("sqlite:///%s" % (tmp_path / "chat.db"))

    first = ChatSession(backend=store)
    view = Driver()
    first.add_connector(view, at=LOCAL)
    await first.start()
    said = await view.say("See the [chart](revenue.html)", attachments=[page()])
    await first.close()

    second = ChatSession(backend=store)
    again = Driver()
    second.add_connector(again, at=LOCAL)
    await second.start()
    link = await second.locate(said, "revenue.html")
    assert link is not None and content(link) == b"<p>up 12%</p>"
    await second.close()


async def test_a_reopened_chat_does_not_overwrite_what_it_archived(tmp_path):
    """Ids are unique across sessions, so a new chat on the same file adds, never replaces."""
    store = DatabaseBackend("sqlite:///%s" % (tmp_path / "chat.db"))

    first = ChatSession(backend=store)
    view = Driver()
    first.add_connector(view, at=LOCAL)
    await first.start()
    kept = await view.say("from the first chat")
    await first.close()

    second = ChatSession(backend=store)
    again = Driver()
    second.add_connector(again, at=LOCAL)
    await second.start()
    said = await again.say("from the second chat")
    await second.close()

    store.initialize()
    archived = {m.id: m.text for m in await store.load()}
    store.shutdown()
    assert kept != said
    assert archived == {kept: "from the first chat", said: "from the second chat"}


# === Who a message was asked of ===================================================

@connector("bot")
@require(HookAnswer)
class _Bot:
    async def answer(self, msg):
        return Reply("hello")


async def test_asked_closed_and_reopened(tmp_path):
    """A say routed to the lone answering peer keeps asked_of in the archive, and in its memory."""
    url = "sqlite:///%s" % (tmp_path / "chat.db")

    first, view = ChatSession(connectors=[_Bot()], backend=DatabaseBackend(url)), Driver()
    first.add_connector(view, at=LOCAL)
    await first.start()
    said = await view.say("hi")
    await first.close()

    bot = _Bot()
    second, again = ChatSession(connectors=[bot], backend=DatabaseBackend(url)), Driver()
    second.add_connector(again, at=LOCAL)
    await second.start()
    reloaded = [m for m in again.context() if m.id == said][0]
    assert (reloaded.to, reloaded.asked_of) == (None, bot.peer_id)
    assert said in [m.id for m in Query(peer=bot.peer_id).select(again.context())]
    await second.close()

