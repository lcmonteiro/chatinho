"""
context(Query(...)): which part of the conversation a peer gets.

See openspec/specs/conversation-context.
"""

from datetime import datetime, timedelta

import pytest

from chatinho import LOCAL, SELF, ChatMessage, MessageID, Query, ReplyStatus


def msg(n: int, frm: int = LOCAL, to=None, reply_to=None, status=ReplyStatus.ANSWERED,
        at=None) -> ChatMessage:
    return ChatMessage(id=MessageID.parse("msg-%016x" % n), text="m%d" % n, frm=frm, to=to,
                       reply_to=None if reply_to is None else MessageID.parse("msg-%016x" % reply_to),
                       status=status, timestamp=at or datetime(2026, 1, 1))


def texts(msgs):
    return [m.text for m in msgs]


# === Query on its own =============================================================

def test_last_twenty_without_errors():
    msgs = [msg(n, status=ReplyStatus.ERROR if n in (3, 7) else ReplyStatus.ANSWERED) for n in range(30)]
    got  = Query(errors=False).last(20).select(msgs)
    kept = [m for m in msgs if m.status != ReplyStatus.ERROR]
    assert texts(got) == texts(kept[-20:])


def test_a_thread():
    a, b, c, d = msg(1), msg(2, reply_to=1), msg(3, reply_to=2), msg(4)
    assert texts(Query(thread=c.id).select([a, b, c, d])) == ["m1", "m2", "m3"]


def test_a_thread_includes_replies_to_its_chain():
    a, b, c, d = msg(1), msg(2, reply_to=1), msg(3, reply_to=1), msg(4, reply_to=3)
    assert texts(Query(thread=b.id).select([a, b, c, d])) == ["m1", "m2", "m3"]


def test_a_peer_and_the_replies_to_it():
    said    = msg(1, frm=3)
    answer  = msg(2, frm=1, reply_to=1)     # a reply to peer 3's message
    to_it   = msg(3, frm=LOCAL, to=3)
    other   = msg(4, frm=1, to=2)
    assert texts(Query(peer=3).select([said, answer, to_it, other])) == ["m1", "m2", "m3"]


def test_what_a_peer_was_asked_is_its_own():
    """A say routed to peer 1 is not addressed to it, and still in its memory."""
    asked = msg(1)
    asked.asked_of = 1
    other = msg(2)
    assert texts(Query(peer=1).select([asked, other])) == ["m1"]


def test_self_is_whoever_asks():
    mine  = [msg(1, frm=LOCAL, to=2), msg(2, frm=2, reply_to=1)]
    other = [msg(3, frm=LOCAL, to=3), msg(4, frm=3, reply_to=3)]
    assert texts(Query(peer=SELF).select(mine + other, asker=2)) == ["m1", "m2"]


def test_self_with_nobody_asking_is_refused():
    with pytest.raises(ValueError):
        Query(peer=SELF).select([msg(1)])


def test_since():
    early, late = datetime(2026, 1, 1), datetime(2026, 1, 2)
    msgs = [msg(1, at=early), msg(2, at=late)]
    assert texts(Query(since=late - timedelta(hours=1)).select(msgs)) == ["m2"]


def test_last_makes_a_copy():
    query = Query(errors=False)
    assert query.last(5).limit == 5 and query.limit is None


# === Through the grant ============================================================

async def test_the_grant_resolves_self_to_the_asker(chat):
    session, view = chat
    await view.say("to everyone")
    assert texts(view.context(Query(peer=SELF))) == ["to everyone"]
    assert view.context(Query(peer=5)) == []


async def test_unchanged_without_a_query(chat):
    session, view = chat
    for n in range(7):
        await view.say("m%d" % n)
    assert texts(view.context()) == ["m%d" % n for n in range(7)]
    assert texts(view.context(Query().last(5))) == ["m2", "m3", "m4", "m5", "m6"]


async def test_a_keyword_is_refused(chat):
    """A Query is the one way to narrow, so each filter has one spelling."""
    session, view = chat
    await view.say("m0")
    with pytest.raises(TypeError):
        view.context(limit=5)
