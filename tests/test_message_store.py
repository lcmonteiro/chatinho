"""Tests for MessageStore.

The store holds no UI state, so unlike the application tests these need no
``run_test()`` and no event loop.
"""

import threading

from chatinho.chat_message import ChatMessage, MessageStore


def message(msg_id: str, text: str = "hi", **kwargs) -> ChatMessage:
    return ChatMessage(id=msg_id, text=text, **kwargs)


def test_new_id_increments():
    store = MessageStore()
    assert [store.new_id() for _ in range(3)] == ["msg-1", "msg-2", "msg-3"]


def test_new_id_is_unique_across_threads():
    store = MessageStore()
    ids: list = []
    lock = threading.Lock()

    def worker():
        mine = [store.new_id() for _ in range(100)]
        with lock:
            ids.extend(mine)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(ids) == 800
    assert len(set(ids)) == 800


def test_add_stores_and_indexes():
    store = MessageStore()
    msg = store.add(message("msg-1", "ola"))
    assert store.messages == [msg]
    assert store.find("msg-1") is msg


def test_find_returns_none_for_unknown_id():
    assert MessageStore().find("msg-999") is None


def test_add_threads_replies():
    store = MessageStore()
    store.add(message("msg-1", "pergunta"))
    store.add(message("msg-2", "resposta", reply_to="msg-1"))
    assert store.replies("msg-1") == ["msg-2"]


def test_replies_is_empty_for_unknown_and_unanswered():
    store = MessageStore()
    store.add(message("msg-1"))
    assert store.replies("msg-1") == []
    assert store.replies("msg-999") == []


def test_replies_returns_a_copy():
    store = MessageStore()
    store.add(message("msg-1"))
    store.add(message("msg-2", reply_to="msg-1"))
    store.replies("msg-1").append("tampered")
    assert store.replies("msg-1") == ["msg-2"]


def test_window_returns_the_tail_oldest_first():
    store = MessageStore()
    for n in range(1, 6):
        store.add(message(f"msg-{n}"))
    assert [m.id for m in store.window(3)] == ["msg-3", "msg-4", "msg-5"]


def test_window_larger_than_history_returns_everything():
    store = MessageStore()
    store.add(message("msg-1"))
    assert [m.id for m in store.window(100)] == ["msg-1"]
    assert MessageStore().window(100) == []


def test_window_does_not_drop_history():
    store = MessageStore()
    for n in range(1, 6):
        store.add(message(f"msg-{n}"))
    store.window(2)
    assert len(store.messages) == 5
    assert store.find("msg-1") is not None
