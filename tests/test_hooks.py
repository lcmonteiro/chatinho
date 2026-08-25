"""Tests for the connector hook system.

Connectors opt into events with ``@hook_point(...)``; the chat triggers every
hook centrally, so a connector that declares no hook points is never called.
"""

import pytest

from chatinho import (
    BaseCommand,
    BaseConnector,
    HOOK_COMMAND_EXECUTED,
    HOOK_MESSAGE_SENT,
    create_chat,
    hook_point,
)


class _Connector(BaseConnector):
    """Connector with the abstract transport methods stubbed out."""

    def __init__(self, name: str = "rec") -> None:
        super().__init__(name)
        self.sent: list = []
        self.executed: list = []

    def initialize(self) -> None:
        pass

    def send(self, message: str, **kwargs) -> None:
        return None

    def receive(self, **kwargs) -> None:
        return None

    def on_message_sent(self, msg, **kwargs) -> None:
        self.sent.append(msg)

    # The signature a handler would naturally declare: it must work on the
    # failure path too, where there is no result.
    def on_command_executed(self, command, result, error, **kwargs) -> None:
        self.executed.append((command, result, error))


@hook_point(HOOK_MESSAGE_SENT, HOOK_COMMAND_EXECUTED)
class RecordingConnector(_Connector):
    """Connector that declares the hooks it records."""


class SilentConnector(_Connector):
    """Same methods, but declares no hook points at all."""


class _Echo(BaseCommand):
    def execute(self, *args, **kwargs) -> str:
        return "ok"


class _Boom(BaseCommand):
    def execute(self, *args, **kwargs):
        raise RuntimeError("kaboom")


@pytest.mark.asyncio
async def test_declared_hook_is_called():
    connector = RecordingConnector()
    app = create_chat(connectors=[connector])
    async with app.run_test():
        app.send_message("ola")
    assert [m.text for m in connector.sent] == ["ola"]


@pytest.mark.asyncio
async def test_connector_without_hook_points_is_never_called():
    connector = SilentConnector()
    app = create_chat(connectors=[connector])
    async with app.run_test():
        app.send_message("ola")
    assert connector.sent == []


@pytest.mark.asyncio
async def test_command_hook_carries_same_keys_on_success_and_failure():
    connector = RecordingConnector()
    app = create_chat(connectors=[connector], commands={"echo": _Echo("echo"), "boom": _Boom("boom")})
    async with app.run_test():
        app.send_command("echo")
        app.send_command("boom")
    assert len(connector.executed) == 2
    assert connector.executed[0] == ("echo", "ok", None)
    command, result, error = connector.executed[1]
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
