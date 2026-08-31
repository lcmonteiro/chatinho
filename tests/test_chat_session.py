"""Tests for ChatSession — the chat driven without a terminal.

Every test here builds a full chat (messages, commands, connectors, backend)
and exercises it synchronously. No ``run_test()``, no event loop, no Textual.
"""

import pytest

from chatinho import (
    HookAsk,
    HookDelete,
    HookExecute,
    HookLoad,
    HookMessageSent,
    HookSave,
    HookSay,
    backend,
    command,
    connector,
    require,
)
from chatinho.chat_session import ChatSession


@command("echo", "echoes its args")
@require(HookExecute)
class _Echo:
    def execute(self, *args, **kwargs) -> str:
        return "echo: %s" % kwargs.get("args", "")


@command("boom", "always fails")
@require(HookExecute)
class _Boom:
    def execute(self, *args, **kwargs):
        raise RuntimeError("kaboom")


@command("spy", "records what it is handed")
@require(HookExecute)
class _Spy:
    def __init__(self) -> None:
        self.seen = None

    def execute(self, chat_instance=None, **kwargs) -> str:
        self.seen = chat_instance
        return "ok"


@connector("rec")
@require(HookAsk)
@require(HookMessageSent)
class _Recorder:
    def __init__(self) -> None:
        self.sent: list = []

    def ask(self, message: str, **kwargs) -> str:
        return "sent: %s" % message

    def on_message_sent(self, msg, **kwargs) -> None:
        self.sent.append(msg.text)


@backend("memory")
@require(HookSave)
@require(HookLoad)
@require(HookDelete)
class _Backend:
    """In-memory backend, enough to exercise the persistence use cases."""

    def __init__(self) -> None:
        self.data: dict = {}
        self.initialized = False

    def initialize(self) -> None:
        self.initialized = True

    def save(self, key, data) -> bool:
        self.data[key] = data
        return True

    def load(self, key):
        return self.data.get(key)

    def delete(self, key) -> bool:
        return self.data.pop(key, None) is not None


# === Messaging ==================================================================


def test_send_and_receive_build_the_history():
    session = ChatSession()
    sent = session.send_message("ola")
    got = session.receive_message("olá de volta", reply_to=sent)
    assert [m.text for m in session.messages] == ["ola", "olá de volta"]
    assert session.messages[0].is_sent_by_me is True
    assert session.messages[1].is_sent_by_me is False
    assert session.get_replies(sent) == [got]


def test_find_message_and_ids():
    session = ChatSession()
    mid = session.send_message("procura-me")
    assert session.find_message(mid).text == "procura-me"
    assert session.find_message("msg-999") is None


# === Observers ==================================================================


def test_observers_fire_in_order_added_then_sent():
    session = ChatSession()
    calls: list = []
    session.on_message_added = lambda msg: calls.append(("added", msg.text))
    session.on_message_sent = lambda msg: calls.append(("sent", msg.text))
    session.send_message("ola")
    assert calls == [("added", "ola"), ("sent", "ola")]


def test_a_session_with_no_observers_still_works():
    session = ChatSession()
    session.send_message("ninguem esta a ver")
    assert len(session.messages) == 1


def test_on_command_replaces_dispatch():
    session = ChatSession(commands=[_Echo()])
    seen: list = []
    session.on_command = seen.append
    session.send_command("echo hello")
    assert seen == ["echo hello"]
    # dispatch was replaced, so no result message was added
    assert len(session.messages) == 1


# === Commands ===================================================================


def test_registered_command_runs_and_its_result_is_displayed():
    session = ChatSession(commands=[_Echo()])
    session.send_command("echo hello")
    assert [m.text for m in session.messages] == ["echo hello", "echo: hello"]


def test_unregistered_command_falls_through_to_the_handler():
    seen: list = []
    session = ChatSession(commands=[_Echo()], command_handler=seen.append)
    session.send_command("stats")
    assert seen == ["stats"]
    assert len(session.messages) == 1


def test_failing_command_is_reported_instead_of_raising():
    session = ChatSession(commands=[_Boom()])
    session.send_command("boom")
    assert "kaboom" in session.messages[-1].text


def test_execute_command_rejects_unknown_names():
    with pytest.raises(ValueError):
        ChatSession().execute_command("nope")


def test_commands_are_handed_the_session_not_a_ui_object():
    """The Dependency Rule: a command must not receive the framework."""
    spy = _Spy()
    session = ChatSession(commands=[spy])
    session.send_command("spy")
    assert spy.seen is session
    assert type(spy.seen).__module__ == "chatinho.chat_session"


# === Connectors and hooks =======================================================


def test_connectors_and_hooks_work_headless():
    connector = _Recorder()
    session = ChatSession(connectors=[connector])
    session.send_message("ola")
    assert connector.sent == ["ola"]
    assert session.ask_connector("rec", "ping") == "sent: ping"


def test_asking_an_unknown_connector_raises():
    with pytest.raises(ValueError):
        ChatSession().ask_connector("nope", "ping")


# === Persistence ================================================================


def test_backend_round_trip():
    backend = _Backend()
    session = ChatSession(backend=backend)
    assert backend.initialized is True
    assert session.save_data("k", {"a": 1}) is True
    assert session.load_data("k") == {"a": 1}
    assert session.delete_data("k") is True
    assert session.load_data("k") is None


def test_persistence_without_a_backend_raises():
    session = ChatSession()
    for call in (
        lambda: session.save_data("k", 1),
        lambda: session.load_data("k"),
        lambda: session.delete_data("k"),
    ):
        with pytest.raises(RuntimeError):
            call()


def test_messages_returns_a_copy():
    """The guarantee holds through the session, not just the store."""
    session = ChatSession()
    session.send_message("guardada")
    session.messages.clear()
    assert [m.text for m in session.messages] == ["guardada"]


# === HookSay: um comando escreve enquanto trabalha ==============================


@command("progress", "writes as it goes")
@require(HookExecute)
@require(HookSay)
class _Progress:
    def execute(self, **kwargs) -> None:
        self.say("a começar")
        self.say("a terminar")


def test_a_command_declaring_hooksay_is_granted_say():
    session = ChatSession(commands=[_Progress()])
    session.send_command("progress")
    assert [m.text for m in session.messages] == ["progress", "a começar", "a terminar"]


def test_a_command_without_hooksay_is_not_granted_it():
    session = ChatSession(commands=[_Echo()])
    assert not hasattr(session.commands["echo"], "say")


def test_the_backend_must_declare_what_the_session_asks_of_it():
    """A capability the backend never had must fail loudly, not silently."""
    @backend("read-only")
    @require(HookLoad)
    class ReadOnly:
        def load(self, key):
            return None

    session = ChatSession(backend=ReadOnly())
    assert session.load_data("k") is None
    for call in (lambda: session.save_data("k", 1), lambda: session.delete_data("k")):
        with pytest.raises(RuntimeError, match="does not declare"):
            call()
