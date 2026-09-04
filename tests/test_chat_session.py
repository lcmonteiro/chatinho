"""Tests for ChatSession — the chat driven without a terminal.

Every test here builds a full chat (messages, commands, connectors, backend)
and exercises it synchronously. No ``run_test()``, no event loop, no Textual.

The conversation is protected, so the tests reach it the way the TUI does:
through a :class:`~tests.conftest.Driver` that declares the hooks and is handed
the capabilities at ``attach``.
"""

import pytest

from conftest import driven

from chatinho import (
    HookAsk,
    HookSendMessage,
    HookDelete,
    HookExecute,
    HookLoad,
    HookReceiveMessage,
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
@require(HookReceiveMessage)
class _Recorder:
    def __init__(self) -> None:
        self.sent: list = []

    def ask(self, message: str, **kwargs) -> str:
        return "sent: %s" % message

    def on_receive_message(self, msg, **kwargs) -> None:
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
    _, view = driven()
    sent = view.send_message("ola")
    got = view.say("olá de volta", reply_to=sent)
    history = view.load_messages()
    assert [m.text for m in history] == ["ola", "olá de volta"]
    assert history[0].is_sent_by_me is True
    assert history[1].is_sent_by_me is False
    assert [m.id for m in history if m.reply_to == sent] == [got]


def test_load_messages_narrows_by_index_and_by_time():
    _, view = driven()
    for n in range(5):
        view.send_message("m%d" % n)
    assert [m.text for m in view.load_messages(limit=2)] == ["m3", "m4"]
    assert [m.text for m in view.load_messages(start=3)] == ["m3", "m4"]
    cut = view.load_messages()[3].timestamp
    assert [m.text for m in view.load_messages(since=cut)] == ["m3", "m4"]
    assert view.load_messages(limit=0) == []


# === Observers ==================================================================


def test_hooks_fire_in_order_received_then_sent():
    _, view = driven()
    view.send_message("ola")
    assert [m.text for m in view.received] == ["ola"]
    assert [m.text for m in view.sent] == ["ola"]


def test_a_plugin_gets_only_what_it_declared():
    """Declaring one hook grants one capability, and nothing else."""

    @require(HookSendMessage)
    class OnlySends:
        send_message: object

    session, _ = driven()
    only = OnlySends()
    session.attach(only)
    only.send_message("basta isto")
    assert not hasattr(only, "load_messages")
    assert not hasattr(only, "say")


def test_the_session_dispatches_whoever_is_watching():
    """on_receive_command is a notice; the registered command runs regardless."""
    session, view = driven()
    session.add_command(_Echo())
    view.send_command("echo hello")
    assert [m.text for m in view.commanded] == ["echo hello"]
    assert [m.text for m in view.load_messages()] == ["echo hello", "echo: hello"]


# === Commands ===================================================================


def test_registered_command_runs_and_its_result_is_displayed():
    _, view = driven(commands=[_Echo()])
    view.send_command("echo hello")
    assert [m.text for m in view.load_messages()] == ["echo hello", "echo: hello"]


def test_unregistered_command_falls_through_to_the_handler():
    seen: list = []
    _, view = driven(commands=[_Echo()], command_handler=seen.append)
    view.send_command("stats")
    assert seen == ["stats"]
    assert len(view.load_messages()) == 1


def test_failing_command_is_reported_instead_of_raising():
    _, view = driven(commands=[_Boom()])
    view.send_command("boom")
    assert "kaboom" in view.load_messages()[-1].text


def test_execute_command_rejects_unknown_names():
    with pytest.raises(ValueError):
        ChatSession().execute_command("nope")


def test_commands_are_handed_the_session_not_a_ui_object():
    """The Dependency Rule: a command must not receive the framework."""
    spy = _Spy()
    session, view = driven(commands=[spy])
    view.send_command("spy")
    assert spy.seen is session
    assert type(spy.seen).__module__ == "chatinho.chat_session"


# === Connectors and hooks =======================================================


def test_connectors_and_hooks_work_headless():
    link = _Recorder()
    session, view = driven(connectors=[link])
    view.send_message("ola")
    assert link.sent == ["ola"]
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


def test_load_messages_returns_a_copy():
    """The guarantee holds through the grant, not just the store."""
    _, view = driven()
    view.send_message("guardada")
    view.load_messages().clear()
    assert [m.text for m in view.load_messages()] == ["guardada"]


# === HookSay: um comando escreve enquanto trabalha ==============================


@command("progress", "writes as it goes")
@require(HookExecute)
@require(HookSay)
class _Progress:
    def execute(self, **kwargs) -> None:
        self.say("a começar")
        self.say("a terminar")


def test_a_command_declaring_hooksay_is_granted_say():
    _, view = driven(commands=[_Progress()])
    view.send_command("progress")
    assert [m.text for m in view.load_messages()] == ["progress", "a começar", "a terminar"]


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
