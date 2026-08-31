"""Tests for chatinho.

The app is built with ``create_chat`` and mounted via ``App.run_test()`` so widgets (input,
chat log) are available to the code under test.
"""

import asyncio
import threading

import pytest
from textual.widgets import Input

from chatinho import HelpCommand, HookExecute, command, create_chat, require


@pytest.mark.asyncio
async def test_new_id_increments():
    app = create_chat()
    async with app.run_test():
        assert app._new_id() == "msg-1"
        assert app._new_id() == "msg-2"


@pytest.mark.asyncio
async def test_send_message_returns_id_and_stores():
    app = create_chat()
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
    app = create_chat()
    received = []
    app.on_command = lambda command: received.append(command)  # type: ignore[method-assign]
    async with app.run_test():
        mid = app.send_command("help")
        assert mid == "msg-1"
        assert app.messages[0].is_command is True
        assert received == ["help"]


@pytest.mark.asyncio
async def test_receive_message_is_not_sent_by_me():
    app = create_chat()
    async with app.run_test():
        mid = app.receive_message("incoming")
        assert mid == "msg-1"
        assert app.messages[0].is_sent_by_me is False


@pytest.mark.asyncio
async def test_reply_threading():
    app = create_chat()
    async with app.run_test():
        original = app.send_message("original")
        reply = app.receive_message("reply text", reply_to=original)
        assert app.get_replies(original) == [reply]
        assert app.messages[-1].reply_to == original


@pytest.mark.asyncio
async def test_get_replies_empty_for_unknown():
    app = create_chat()
    async with app.run_test():
        assert app.get_replies("msg-999") == []


@pytest.mark.asyncio
async def test_receive_message_from_other_thread():
    """receive_message is safe to call from a worker thread."""
    app = create_chat()
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
    app = create_chat()
    async with app.run_test():
        mid = app.send_message("find me")
        found = app._find_message(mid)
        assert found is not None and found.text == "find me"
        assert app._find_message("msg-999") is None


@pytest.mark.asyncio
async def test_send_pending_reply_without_target_returns_none():
    app = create_chat()
    async with app.run_test():
        assert app.send_pending_reply("text") is None
        assert len(app.messages) == 0


@pytest.mark.asyncio
async def test_send_pending_reply_after_click_target():
    app = create_chat()
    async with app.run_test():
        original = app.receive_message("target")
        app._set_reply_target(original)
        mid = app.send_pending_reply("answer")
        assert mid is not None
        assert app.messages[-1].reply_to == original
        assert app._reply_target is None


@pytest.mark.asyncio
async def test_clear_reply_target_restores_placeholder():
    app = create_chat()
    async with app.run_test():
        original = app.receive_message("target")
        app._set_reply_target(original)
        assert app._reply_target == original
        app._clear_reply_target()
        assert app._reply_target is None
        assert app._input_placeholder == "Type a message or /command"


@pytest.mark.asyncio
async def test_input_focused_on_mount():
    app = create_chat()
    async with app.run_test():
        inp = app.query_one("#input-line", Input)
        assert inp.has_focus


@pytest.mark.asyncio
async def test_submit_text_sends_message():
    app = create_chat()
    async with app.run_test() as pilot:
        inp = app.query_one("#input-line", Input)
        inp.value = "hello world"
        await pilot.press("enter")
        assert len(app.messages) == 1
        assert app.messages[0].text == "hello world"


@pytest.mark.asyncio
async def test_submit_command_sends_command():
    app = create_chat()
    async with app.run_test() as pilot:
        inp = app.query_one("#input-line", Input)
        inp.value = "/help"
        await pilot.press("enter")
        assert len(app.messages) == 1
        assert app.messages[0].is_command is True


@pytest.mark.asyncio
async def test_registered_command_is_executed_and_result_displayed():
    app = create_chat(commands=[HelpCommand()])
    async with app.run_test():
        app.send_command("help")
        assert len(app.messages) == 2
        assert app.messages[0].is_command is True
        result = app.messages[1]
        assert result.is_sent_by_me is False
        assert "/help" in result.text


@pytest.mark.asyncio
async def test_failing_command_is_reported_instead_of_raising():
    @command("boom", "always fails")
    @require(HookExecute)
    class Boom:
        def execute(self, *args, **kwargs):
            raise RuntimeError("kaboom")

    app = create_chat(commands=[Boom()])
    async with app.run_test():
        app.send_command("boom")
        assert len(app.messages) == 2
        assert "kaboom" in app.messages[1].text


@pytest.mark.asyncio
async def test_welcome_message_is_shown_on_mount():
    app = create_chat(welcome_message="ola")
    async with app.run_test():
        assert [m.text for m in app.messages] == ["ola"]
        assert app.messages[0].is_sent_by_me is False


@pytest.mark.asyncio
async def test_no_welcome_message_by_default():
    app = create_chat()
    async with app.run_test():
        assert app.messages == []


@pytest.mark.asyncio
async def test_messages_added_before_mount_are_kept_and_rendered():
    app = create_chat()
    assert app.receive_message("early") == "msg-1"
    assert [m.text for m in app.messages] == ["early"]
    async with app.run_test():
        assert app._rendered_msg_ids == ["msg-1"]
        assert app._find_message("msg-1") is not None
