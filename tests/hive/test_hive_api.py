"""
Tests for the hive's API: keys, a chat's own records, and the admin's views.

See src/chatinho/hive/docs/spec.md.
"""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from chatinho import ChatTrace, TraceID, TraceState
from chatinho.hive import create_app
from chatinho.support.parts.hive import KEY_HEADER, message_from_wire, trace_to_wire, trace_from_wire
from fakes.hive import make_hive, message, wire_messages


@pytest.fixture
def hive(tmp_path):
    hive = make_hive(tmp_path, "a", "b")
    with TestClient(create_app(hive.db)) as client:
        hive.client = client                      # type: ignore[attr-defined]
        yield hive


def as_(key: str) -> dict:
    return {KEY_HEADER: key}


def post(hive, chat: str, *messages):
    return hive.client.post("/api/messages", json={"messages": wire_messages(*messages)},
                            headers=as_(hive.keys[chat]))


def loaded(hive, chat: str, **params):
    answer = hive.client.get("/api/messages", params=params, headers=as_(hive.keys[chat]))
    assert answer.status_code == 200, answer.text
    return [message_from_wire(m) for m in answer.json()["messages"]]


def a_trace(msg, prev=None, n=0, state=TraceState.RUNNING) -> ChatTrace:
    return ChatTrace(id=TraceID.new(), msg_id=msg.id, state=state, text="step %d" % n, frm=1, prev=prev,
                     timestamp=msg.timestamp + timedelta(seconds=n))


def traces_of(hive, msg):
    answer = hive.client.get("/api/chats/a/messages/%s/traces" % msg.id, headers=as_(hive.admin))
    return answer.json()["traces"]


def post_traces(hive, chat: str, *traces):
    return hive.client.post("/api/traces", json={"traces": [trace_to_wire(t, "dev") for t in traces]},
                            headers=as_(hive.keys[chat]))


# @ac AC-HIVE-003.1
def test_no_key_is_401(hive):
    assert hive.client.get("/api/messages").status_code == 401
    assert hive.client.post("/api/messages", json={"messages": []}).status_code == 401
    assert hive.client.get("/api/chats").status_code == 401


# @ac AC-HIVE-003.2
def test_an_unknown_key_is_401(hive):
    assert hive.client.get("/api/messages", headers=as_("hive_" + "0" * 48)).status_code == 401
    assert hive.client.get("/api/chats", headers=as_("nonsense")).status_code == 401


# @ac AC-HIVE-003.3
def test_a_chat_key_cannot_use_the_admin_views(hive):
    key = as_(hive.keys["a"])
    assert hive.client.get("/api/chats", headers=key).status_code == 403
    assert hive.client.get("/api/chats/b/messages", headers=key).status_code == 403
    assert hive.client.get("/api/chats/a/messages", headers=key).status_code == 403


# @ac AC-HIVE-003.4
def test_writes_land_in_the_keys_chat(hive):
    msg = message(1, "for a only")
    assert post(hive, "a", msg).status_code == 200
    assert [m.id for m in loaded(hive, "a")] == [msg.id]
    assert loaded(hive, "b") == []


# @ac AC-HIVE-004.1
def test_post_and_load_the_last_two_oldest_first_with_every_field(hive):
    first  = message(1)
    second = message(2, frm=1, to=0, reply_to=first.id)
    third  = message(3, frm=2)
    assert post(hive, "a", first, second, third).json() == {"stored": 3}
    got = loaded(hive, "a", limit=2)
    assert got == [second, third]
    assert [(m.frm, m.to, m.reply_to, m.timestamp, m.status) for m in got] == \
        [(m.frm, m.to, m.reply_to, m.timestamp, m.status) for m in (second, third)]


# @ac AC-HIVE-004.1
def test_load_since_a_time(hive):
    messages = [message(n) for n in range(1, 6)]
    post(hive, "a", *messages)
    got = loaded(hive, "a", since=messages[2].timestamp.isoformat())
    assert [m.id for m in got] == [m.id for m in messages[2:]]


# @ac AC-HIVE-004.2
def test_a_resend_is_not_a_duplicate(hive):
    msg = message(1)
    post(hive, "a", msg)
    assert post(hive, "a", msg).json() == {"stored": 0}
    assert [m.id for m in loaded(hive, "a")] == [msg.id]


# @ac AC-HIVE-004.3
def test_forget_drops_the_older_messages_their_attachments_and_traces(hive):
    messages = [message(n) for n in range(1, 6)]
    post(hive, "a", *messages)
    old = messages[0]
    hive.client.put("/api/messages/%s/attachments/notes.md" % old.id, content=b"# notes",
                    headers={**as_(hive.keys["a"]), "Content-Type": "text/markdown"})
    post_traces(hive, "a", a_trace(old))
    answer = hive.client.delete("/api/messages", params={"before": messages[2].timestamp.isoformat()},
                                headers=as_(hive.keys["a"]))
    assert answer.json() == {"forgotten": 2}
    assert [m.id for m in loaded(hive, "a")] == [m.id for m in messages[2:]]
    assert hive.client.get("/api/messages/%s/attachments/notes.md" % old.id,
                           headers=as_(hive.keys["a"])).status_code == 404
    assert hive.client.get("/api/chats/a/messages/%s/traces" % old.id,
                           headers=as_(hive.admin)).status_code == 404


# @ac AC-HIVE-004.4
def test_a_bad_batch_is_422_and_nothing_is_stored(hive):
    good = wire_messages(message(1))[0]
    bad  = dict(wire_messages(message(2))[0])
    del bad["id"]
    answer = hive.client.post("/api/messages", json={"messages": [good, bad]}, headers=as_(hive.keys["a"]))
    assert answer.status_code == 422
    assert loaded(hive, "a") == []
    for nonsense in ({"messages": "no"}, {"nothing": []}, [1, 2]):
        assert hive.client.post("/api/messages", json=nonsense,
                                headers=as_(hive.keys["a"])).status_code == 422


# @ac AC-HIVE-005.1
def test_an_attachment_comes_back_byte_for_byte(hive):
    msg  = message(1)
    data = bytes(range(256))
    post(hive, "a", msg)
    put = hive.client.put("/api/messages/%s/attachments/blob.bin" % msg.id, content=data,
                          headers={**as_(hive.keys["a"]), "Content-Type": "application/octet-stream"})
    assert put.status_code == 204
    got = hive.client.get("/api/messages/%s/attachments/blob.bin" % msg.id, headers=as_(hive.keys["a"]))
    assert got.status_code == 200
    assert got.content == data
    assert got.headers["content-type"].startswith("application/octet-stream")


# @ac AC-HIVE-005.2
def test_an_attachment_never_put_is_404(hive):
    msg = message(1)
    post(hive, "a", msg)
    assert hive.client.get("/api/messages/%s/attachments/none.md" % msg.id,
                           headers=as_(hive.keys["a"])).status_code == 404


# @ac AC-HIVE-005.2
def test_another_chats_attachment_is_404(hive):
    msg = message(1)
    post(hive, "a", msg)
    hive.client.put("/api/messages/%s/attachments/notes.md" % msg.id, content=b"x",
                    headers={**as_(hive.keys["a"]), "Content-Type": "text/markdown"})
    assert hive.client.get("/api/messages/%s/attachments/notes.md" % msg.id,
                           headers=as_(hive.keys["b"])).status_code == 404


# @ac AC-HIVE-005.3
def test_traces_are_kept_with_every_field_and_a_resend_is_not_a_duplicate(hive):
    msg    = message(1)
    first  = a_trace(msg, n=1)
    second = a_trace(msg, prev=first.id, n=2, state=TraceState.DONE)
    post(hive, "a", msg)
    assert post_traces(hive, "a", first, second).json() == {"stored": 2}
    assert post_traces(hive, "a", first, second).json() == {"stored": 0}
    got = traces_of(hive, msg)
    assert [trace_from_wire(t) for t in got] == [first, second]
    assert got[1]["prev"] == str(first.id)
    assert {t["frm_name"] for t in got} == {"dev"}


# @ac AC-HIVE-005.4
def test_a_trace_before_its_message_is_kept(hive):
    msg   = message(1)
    trace = a_trace(msg)
    assert post_traces(hive, "a", trace).status_code == 200
    post(hive, "a", msg)
    got = traces_of(hive, msg)
    assert [trace_from_wire(t) for t in got] == [trace]


# @ac AC-HIVE-006.1
def test_the_list_of_chats_with_counts_and_last_write(hive):
    post(hive, "a", message(1), message(2))
    chats = {c["name"]: c for c in hive.client.get("/api/chats", headers=as_(hive.admin)).json()["chats"]}
    assert set(chats) == {"a", "b"}
    assert chats["a"]["messages"] == 2 and chats["a"]["last"] is not None
    assert chats["b"]["messages"] == 0


# @ac AC-HIVE-006.2
def test_an_admin_reads_a_chats_messages_oldest_first(hive):
    messages = [message(n) for n in (3, 1, 2)]
    post(hive, "a", *messages)
    answer = hive.client.get("/api/chats/a/messages", headers=as_(hive.admin))
    got    = [message_from_wire(m) for m in answer.json()["messages"]]
    assert [m.text for m in got] == ["message 1", "message 2", "message 3"]
    assert all(m["frm_name"] == "me" for m in answer.json()["messages"])
    limited = hive.client.get("/api/chats/a/messages", params={"limit": 1}, headers=as_(hive.admin))
    assert [m["text"] for m in limited.json()["messages"]] == ["message 3"]


# @ac AC-HIVE-006.3
def test_a_messages_traces_oldest_first_with_their_prev(hive):
    msg   = message(1)
    root  = a_trace(msg, n=1)
    left  = a_trace(msg, prev=root.id, n=2)
    right = a_trace(msg, prev=root.id, n=3)
    post(hive, "a", msg)
    post_traces(hive, "a", right, root, left)
    got = traces_of(hive, msg)
    assert [t["id"] for t in got] == [str(root.id), str(left.id), str(right.id)]
    assert [t["prev"] for t in got] == [None, str(root.id), str(root.id)]


# @ac AC-HIVE-006.4
def test_an_unknown_chat_or_message_is_404(hive):
    assert hive.client.get("/api/chats/nobody/messages", headers=as_(hive.admin)).status_code == 404
    assert hive.client.get("/api/chats/nobody/messages/msg-0123456789abcdef/traces",
                           headers=as_(hive.admin)).status_code == 404


# @ac AC-HIVE-009.1
def test_the_api_is_described(hive):
    spec  = hive.client.get("/openapi.json").json()
    paths = spec["paths"]
    for path in ("/api/messages", "/api/messages/{msg_id}/attachments/{name}", "/api/traces", "/api/chats",
                 "/api/chats/{name}/messages", "/api/chats/{name}/messages/{msg_id}/traces",
                 "/api/chats/{name}/stream"):
        assert path in paths, path
    assert "X-Hive-Key" in repr(spec)
    assert hive.client.get("/docs").status_code == 200
