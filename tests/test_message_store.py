"""Tests for MessageStore.

The store holds no UI state, so unlike the application tests these need no
``run_test()`` and no event loop.
"""

import re
import threading

import pytest

from chatinho.chat_message import ChatMessage, MessageStore, short_id


def message(msg_id: str, text: str = "hi", **kwargs) -> ChatMessage:
    return ChatMessage(id=msg_id, text=text, **kwargs)


def test_new_id_is_msg_and_sixteen_hex_characters():
    store = MessageStore()
    assert all(re.fullmatch(r"msg-[0-9a-f]{16}", store.new_id()) for _ in range(100))


def test_new_id_is_unique_across_threads():
    store = MessageStore()
    ids: list = []
    lock = threading.Lock()

    def worker():
        mine = [store.new_id() for _ in range(1250)]
        with lock:
            ids.extend(mine)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(ids) == 10000
    assert len(set(ids)) == 10000


def test_short_id_is_the_first_seven_hex_characters():
    assert short_id("msg-3f9a1c2e7b04d5a6") == "3f9a1c2"


@pytest.mark.parametrize("msg_id", ["msg-3", "abc", "msg-3f9a1c2e7b04d5a", "msg-3F9A1C2E7B04D5A6"])
def test_short_id_leaves_other_ids_alone(msg_id):
    assert short_id(msg_id) == msg_id


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

def test_messages_returns_a_copy():
    """Same guarantee as replies(): callers cannot edit the history by accident."""
    store = MessageStore()
    store.add(message("msg-1", "guardada"))
    store.messages.clear()
    store.messages.append(message("msg-2", "intrusa"))
    assert [m.text for m in store.messages] == ["guardada"]


def test_the_copy_shares_the_messages_themselves():
    """Only the list is copied — the ChatMessage objects are the same ones."""
    store = MessageStore()
    stored = store.add(message("msg-1"))
    assert store.messages[0] is stored
