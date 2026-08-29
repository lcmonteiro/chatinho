"""Tests for HookRegistry — the dispatch half of the hook system.

Like the store, the registry is Textual-free: these run without an app.
"""

import logging

from chatinho import BaseConnector, HOOK_MESSAGE_SENT, hook_point
from chatinho.chat_hooks import HookRegistry


class _Connector(BaseConnector):
    def __init__(self, name: str = "c") -> None:
        super().__init__(name)
        self.seen: list = []

    def initialize(self) -> None:
        pass

    def send(self, message: str, **kwargs) -> None:
        return None

    def on_message_sent(self, msg, **kwargs) -> None:
        self.seen.append(msg)


@hook_point(HOOK_MESSAGE_SENT)
class Declared(_Connector):
    """Declares the hook it implements."""


class Undeclared(_Connector):
    """Implements the method but never opts in."""


@hook_point(HOOK_MESSAGE_SENT)
class Exploding(_Connector):
    def on_message_sent(self, msg, **kwargs) -> None:
        raise RuntimeError("kaboom")


def test_declared_connector_receives_the_payload():
    registry = HookRegistry()
    connector = Declared()
    registry.register(connector)
    registry.trigger(HOOK_MESSAGE_SENT, msg="ola")
    assert connector.seen == ["ola"]


def test_undeclared_connector_is_never_called():
    registry = HookRegistry()
    connector = Undeclared()
    registry.register(connector)
    registry.trigger(HOOK_MESSAGE_SENT, msg="ola")
    assert connector.seen == []
    assert registry.connectors_for(HOOK_MESSAGE_SENT) == []


def test_unregister_drops_the_connector():
    registry = HookRegistry()
    connector = Declared()
    registry.register(connector)
    registry.unregister(connector)
    registry.trigger(HOOK_MESSAGE_SENT, msg="ola")
    assert connector.seen == []


def test_unregister_only_drops_the_named_object():
    registry = HookRegistry()
    kept, dropped = Declared("kept"), Declared("dropped")
    registry.register(kept)
    registry.register(dropped)
    registry.unregister(dropped)
    registry.trigger(HOOK_MESSAGE_SENT, msg="ola")
    assert kept.seen == ["ola"]
    assert dropped.seen == []


def test_a_raising_connector_does_not_stop_the_others(caplog):
    registry = HookRegistry()
    boom, ok = Exploding("boom"), Declared("ok")
    registry.register(boom)
    registry.register(ok)
    with caplog.at_level(logging.ERROR):
        registry.trigger(HOOK_MESSAGE_SENT, msg="ola")
    assert ok.seen == ["ola"]
    assert "kaboom" in caplog.text


def test_unknown_hook_name_warns_instead_of_raising(caplog):
    registry = HookRegistry()
    with caplog.at_level(logging.WARNING):
        registry.trigger("not_a_hook", msg="ola")
    assert "Unknown hook name" in caplog.text
