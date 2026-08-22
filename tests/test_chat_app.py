"""Tests for chatinho.

The Textual app is mounted via ``App.run_test()`` so widgets (input,
chat log) are available to the code under test.
"""

import asyncio
import threading

import pytest
from textual.widgets import Input

from chatinho import ChatApp


@pytest.mark.asyncio
async def test_new_id_increments():
    app = ChatApp()
    async with app.run_test():
        assert app._new_id() == "msg-1"
        assert app._new_id() == "msg-2"


@pytest.mark.asyncio
async def test_send_message_returns_id_and_stores():
    app = ChatApp()
    async with app.run_test():
        mid = app.send_message("hello")
        assert mid == "msg-1"
        assert len(app.messages) == 1
        msg = app.messages[0]
        assert msg.text == "hello"
        assert msg.is_sent_by_me is True
        assert msg.is_command is False


@pytest.mark.asyncio
async def test_send_command_sets_flag_and_calls_hook():
    app = ChatApp()
    received = []
    app.on_command = lambda command: received.append(command)  # type: ignore[method-assign]
    async with app.run_test():
        mid = app.send_command("help")
        assert mid == "msg-1"
        assert app.messages[0].is_command is True
        assert received == ["help"]


@pytest.mark.asyncio
async def test_receive_message_is_not_sent_by_me():
    app = ChatApp()
    async with app.run_test():
        mid = app.receive_message("incoming")
        assert mid == "msg-1"
        assert app.messages[0].is_sent_by_me is False


@pytest.mark.asyncio
async def test_reply_threading():
    app = ChatApp()
    async with app.run_test():
        original = app.send_message("original")
        reply = app.receive_message("reply text", reply_to=original)
        assert app.get_replies(original) == [reply]
        assert app.messages[-1].reply_to == original


@pytest.mark.asyncio
async def test_get_replies_empty_for_unknown():
    app = ChatApp()
    async with app.run_test():
        assert app.get_replies("msg-999") == []


@pytest.mark.asyncio
async def test_receive_message_from_other_thread():
    """receive_message is safe to call from a worker thread."""
    app = ChatApp()
    async with app.run_test():
        assert app._app_thread_id == threading.get_ident()
        results = {}

        def worker():
            results["id"] = app.receive_message("from thread")

        t = threading.Thread(target=worker)
        t.start()
        # call_from_thread blocks the worker until the app's event loop
        # processes the callback — yield to the loop so it can land.
        for _ in range(100):
            if not t.is_alive():
                break
            await asyncio.sleep(0.01)
        assert not t.is_alive()
        assert results["id"] == "msg-1"
        assert len(app.messages) == 1
        assert app.messages[0].text == "from thread"
        assert app.messages[0].is_sent_by_me is False


@pytest.mark.asyncio
async def test_find_message():
    app = ChatApp()
    async with app.run_test():
        mid = app.send_message("find me")
        found = app._find_message(mid)
        assert found is not None and found.text == "find me"
        assert app._find_message("msg-999") is None


@pytest.mark.asyncio
async def test_send_pending_reply_without_target_returns_none():
    app = ChatApp()
    async with app.run_test():
        assert app.send_pending_reply("text") is None
        assert len(app.messages) == 0


@pytest.mark.asyncio
async def test_send_pending_reply_after_click_target():
    app = ChatApp()
    async with app.run_test():
        original = app.receive_message("target")
        app._set_reply_target(original)
        mid = app.send_pending_reply("answer")
        assert mid is not None
        assert app.messages[-1].reply_to == original
        assert app._reply_target is None


@pytest.mark.asyncio
async def test_clear_reply_target_restores_placeholder():
    app = ChatApp()
    async with app.run_test():
        original = app.receive_message("target")
        app._set_reply_target(original)
        assert app._reply_target == original
        app._clear_reply_target()
        assert app._reply_target is None
        assert app._input_placeholder == "Type a message or /command"


@pytest.mark.asyncio
async def test_input_focused_on_mount():
    app = ChatApp()
    async with app.run_test():
        inp = app.query_one("#input-line", Input)
        assert inp.has_focus


@pytest.mark.asyncio
async def test_submit_text_sends_message():
    app = ChatApp()
    async with app.run_test() as pilot:
        inp = app.query_one("#input-line", Input)
        inp.value = "hello world"
        await pilot.press("enter")
        assert len(app.messages) == 1
        assert app.messages[0].text == "hello world"


@pytest.mark.asyncio
async def test_submit_command_sends_command():
    app = ChatApp()
    async with app.run_test() as pilot:
        inp = app.query_one("#input-line", Input)
        inp.value = "/help"
        await pilot.press("enter")
        assert len(app.messages) == 1
        assert app.messages[0].is_command is True
