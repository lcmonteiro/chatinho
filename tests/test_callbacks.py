"""Tests for ChatApp callbacks (hooks).

A small ``MockChatApp`` subclass records every hook invocation so the
tests can assert *what* fired, *when*, and *with which payload* —
without needing a real transport.
"""

import pytest
from textual.widgets import Input

from chatinho import ChatApp, ChatMessage


class MockChatApp(ChatApp):
    """ChatApp whose hooks record (kind, payload) into ``self.calls``."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.calls: list[tuple[str, object]] = []

    def on_command(self, command: str) -> None:
        self.calls.append(("command", command))

    def on_message_sent(self, msg: ChatMessage) -> None:
        self.calls.append(("sent", msg))

    def on_message_received(self, msg: ChatMessage) -> None:
        self.calls.append(("received", msg))


# === command_handler (default on_command delegate) ============================


@pytest.mark.asyncio
async def test_command_handler_receives_command_without_prefix():
    commands: list[str] = []
    app = ChatApp(command_handler=commands.append)
    async with app.run_test():
        app.send_command("help")
    assert commands == ["help"]


@pytest.mark.asyncio
async def test_command_handler_not_called_for_normal_message():
    commands: list[str] = []
    app = ChatApp(command_handler=commands.append)
    async with app.run_test():
        app.send_message("hello")
    assert commands == []


@pytest.mark.asyncio
async def test_command_handler_receives_command_as_given():
    # send_command() receives the command without the '/' prefix and
    # passes it through unchanged; trimming is the input layer's job.
    commands: list[str] = []
    app = ChatApp(command_handler=commands.append)
    async with app.run_test():
        app.send_command("  help  ")
    assert commands == ["  help  "]


@pytest.mark.asyncio
async def test_input_submission_trims_command_before_handler():
    commands: list[str] = []
    app = ChatApp(command_handler=commands.append)
    async with app.run_test() as pilot:
        inp = app.query_one("#input-line", Input)
        inp.value = "  /help  "
        await pilot.press("enter")
    assert commands == ["help"]


@pytest.mark.asyncio
async def test_on_command_override_skips_handler_unless_super():
    commands: list[str] = []

    class SilencingApp(ChatApp):
        def on_command(self, command: str) -> None:
            del command  # swallow: do not delegate

    app = SilencingApp(command_handler=commands.append)
    async with app.run_test():
        app.send_command("help")
    assert commands == []


# === on_command / on_message_sent (send_command) ==============================


@pytest.mark.asyncio
async def test_send_command_fires_command_then_sent():
    app = MockChatApp()
    async with app.run_test():
        app.send_command("list")
    kinds = [kind for kind, _ in app.calls]
    assert kinds == ["command", "sent"]
    command = app.calls[0][1]
    msg = app.calls[1][1]
    assert command == "list"
    assert isinstance(msg, ChatMessage)
    assert msg.text == "list"
    assert msg.is_command is True
    assert msg.is_sent_by_me is True
    assert msg.id == "msg-1"


@pytest.mark.asyncio
async def test_send_command_fires_hooks_only_after_message_stored():
    app = MockChatApp()
    async with app.run_test():
        app.send_command("list")
    assert len(app.messages) == 1
    assert app.messages[0].is_command is True


# === on_message_sent (send_message) ===========================================


@pytest.mark.asyncio
async def test_send_message_fires_sent_hook():
    app = MockChatApp()
    async with app.run_test():
        app.send_message("ola")
    assert len(app.calls) == 1
    kind, msg = app.calls[0]
    assert kind == "sent"
    assert isinstance(msg, ChatMessage)
    assert msg.text == "ola"
    assert msg.is_command is False
    assert msg.is_sent_by_me is True


@pytest.mark.asyncio
async def test_send_message_sent_hook_carries_reply_to():
    app = MockChatApp()
    async with app.run_test():
        original = app.receive_message("target")
        app.send_message("resposta", reply_to=original)
    sent = [m for kind, m in app.calls if kind == "sent"]
    assert len(sent) == 1
    assert sent[0].reply_to == original


# === on_message_received (receive_message) ====================================


@pytest.mark.asyncio
async def test_receive_message_fires_received_hook():
    app = MockChatApp()
    async with app.run_test():
        app.receive_message("incoming")
    assert len(app.calls) == 1
    kind, msg = app.calls[0]
    assert kind == "received"
    assert isinstance(msg, ChatMessage)
    assert msg.text == "incoming"
    assert msg.is_sent_by_me is False
    assert msg.is_command is False


@pytest.mark.asyncio
async def test_receive_message_hook_carries_reply_to_and_threads():
    app = MockChatApp()
    async with app.run_test():
        original = app.send_message("pergunta")
        app.receive_message("resposta", reply_to=original)
    received = [m for kind, m in app.calls if kind == "received"]
    assert len(received) == 1
    assert received[0].reply_to == original
    assert app.get_replies(original) == [received[0].id]


# === hooks fire on input submission (end-to-end) ==============================


@pytest.mark.asyncio
async def test_submitting_text_fires_sent_hook():
    app = MockChatApp()
    async with app.run_test() as pilot:
        inp = app.query_one("#input-line", Input)
        inp.value = "pelo input"
        await pilot.press("enter")
    kinds = [kind for kind, _ in app.calls]
    assert kinds == ["sent"]
    msg = app.calls[0][1]
    assert msg.text == "pelo input"
    assert msg.is_command is False


@pytest.mark.asyncio
async def test_submitting_command_fires_command_and_sent_hooks():
    app = MockChatApp()
    async with app.run_test() as pilot:
        inp = app.query_one("#input-line", Input)
        inp.value = "/stats"
        await pilot.press("enter")
    kinds = [kind for kind, _ in app.calls]
    assert kinds == ["command", "sent"]
    assert app.calls[0][1] == "stats"
    assert app.calls[1][1].is_command is True
