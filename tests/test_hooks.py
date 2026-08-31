"""Tests for the connector hook system.

Connectors opt into events with ``@require(...)``; the chat triggers every
hook centrally, so a connector that declares no hook points is never called.
"""

import pytest

from chatinho import (
    HookExecute,
    command,
    HookAsk,
    HookCommandExecuted,
    HookMessageSent,
    create_chat,
    require,
)


class _Connector:
    """The methods, without any declaration."""

    def __init__(self, name: str = "rec") -> None:
        self.name = name
        self.sent: list = []
        self.executed: list = []

    def ask(self, message: str, **kwargs) -> None:
        return None

    def on_message_sent(self, msg, **kwargs) -> None:
        self.sent.append(msg)

    # The signature a handler would naturally declare: it must work on the
    # failure path too, where there is no result.
    def on_command_executed(self, command, result, error, **kwargs) -> None:
        self.executed.append((command, result, error))


@require(HookAsk)
@require(HookMessageSent)
@require(HookCommandExecuted)
class RecordingConnector(_Connector):
    """Connector that declares the hooks it records."""


class SilentConnector(_Connector):
    """Same methods, but declares nothing at all."""


@command("echo", "")
@require(HookExecute)
class _Echo:
    def execute(self, *args, **kwargs) -> str:
        return "ok"


@command("boom", "")
@require(HookExecute)
class _Boom:
    def execute(self, *args, **kwargs):
        raise RuntimeError("kaboom")


@pytest.mark.asyncio
async def test_declared_hook_is_called():
    link = RecordingConnector()
    app = create_chat(connectors=[link])
    async with app.run_test():
        app.send_message("ola")
    assert [m.text for m in link.sent] == ["ola"]


@pytest.mark.asyncio
async def test_a_connector_that_declares_nothing_is_never_called():
    link = SilentConnector()
    app = create_chat(connectors=[link])
    async with app.run_test():
        app.send_message("ola")
    assert link.sent == []


@pytest.mark.asyncio
async def test_command_hook_carries_same_keys_on_success_and_failure():
    link = RecordingConnector()
    app = create_chat(connectors=[link], commands=[_Echo(), _Boom()])
    async with app.run_test():
        app.send_command("echo")
        app.send_command("boom")
    assert len(link.executed) == 2
    assert link.executed[0] == ("echo", "ok", None)
    command, result, error = link.executed[1]
    assert (command, result) == ("boom", None)
    assert isinstance(error, RuntimeError)


@pytest.mark.asyncio
async def test_replacing_a_connector_drops_the_old_one_from_the_hooks():
    old = RecordingConnector("dup")
    new = RecordingConnector("dup")
    app = create_chat(connectors=[old])
    async with app.run_test():
        app.add_connector(new)
        app.send_message("ola")
    assert app.connectors["dup"] is new
    assert len(app.connectors) == 1
    assert old.sent == []
    assert [m.text for m in new.sent] == ["ola"]
