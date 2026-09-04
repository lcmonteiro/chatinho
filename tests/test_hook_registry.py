"""Tests for HookRegistry — the dispatch half of the hook system.

Like the store, the registry is Textual-free: these run without an app.
"""

import logging

from chatinho import HookAsk, HookReceiveMessage, require
from chatinho.chat_hooks import HookRegistry


class _Connector:
    """The methods, without any declaration."""

    def __init__(self, name: str = "c") -> None:
        self.name = name
        self.seen: list = []

    def ask(self, message: str, **kwargs) -> None:
        return None

    def on_receive_message(self, msg, **kwargs) -> None:
        self.seen.append(msg)


@require(HookAsk)
@require(HookReceiveMessage)
class Declared(_Connector):
    """Declares the hook it implements."""


class Undeclared(_Connector):
    """Implements the method but never declares it."""


@require(HookReceiveMessage)
class Exploding(_Connector):
    def on_receive_message(self, msg, **kwargs) -> None:
        raise RuntimeError("kaboom")


def test_declared_connector_receives_the_payload():
    registry = HookRegistry()
    link = Declared()
    registry.register(link)
    registry.trigger(HookReceiveMessage, msg="ola")
    assert link.seen == ["ola"]


def test_undeclared_connector_is_never_called():
    registry = HookRegistry()
    link = Undeclared()
    registry.register(link)
    registry.trigger(HookReceiveMessage, msg="ola")
    assert link.seen == []
    assert registry.connectors_for(HookReceiveMessage) == []


def test_unregister_drops_the_connector():
    registry = HookRegistry()
    link = Declared()
    registry.register(link)
    registry.unregister(link)
    registry.trigger(HookReceiveMessage, msg="ola")
    assert link.seen == []


def test_unregister_only_drops_the_named_object():
    registry = HookRegistry()
    kept, dropped = Declared("kept"), Declared("dropped")
    registry.register(kept)
    registry.register(dropped)
    registry.unregister(dropped)
    registry.trigger(HookReceiveMessage, msg="ola")
    assert kept.seen == ["ola"]
    assert dropped.seen == []


def test_a_raising_connector_does_not_stop_the_others(caplog):
    registry = HookRegistry()
    boom, ok = Exploding("boom"), Declared("ok")
    registry.register(boom)
    registry.register(ok)
    with caplog.at_level(logging.ERROR):
        registry.trigger(HookReceiveMessage, msg="ola")
    assert ok.seen == ["ola"]
    assert "kaboom" in caplog.text


def test_an_undeclared_hook_dispatches_to_nobody(caplog):
    from chatinho import HookReceiveCommand
    registry = HookRegistry()
    registry.register(Declared())
    registry.trigger(HookReceiveCommand, msg=None)
    assert registry.connectors_for(HookReceiveCommand) == []
