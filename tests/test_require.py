"""Tests for @connector and @require — how a connector says what it does.

There is no base class. A connector is a plain object that declares its
capabilities, and ``require`` checks at class-definition time that it
implements them, so a missing or misspelled method is an import error rather
than a hook that silently never fires.
"""

import pytest

from chatinho import (
    A2AConnector,
    ChatSession,
    HookAnswer,
    HookAsk,
    HookMessageSent,
    OpenAIConnector,
    connector,
    require,
)
from chatinho.chat_hooks import declares, hooks_of, name_of


# === @require validates ==========================================================


def test_a_class_that_implements_what_it_declares_is_accepted():
    @require(HookAsk)
    class Fine:
        def ask(self, message, **kwargs):
            return "ok"

    assert declares(Fine(), HookAsk)


def test_a_missing_method_is_an_error_at_class_definition():
    with pytest.raises(TypeError, match=r"declares HookAnswer.*does not implement answer\(\)"):
        @require(HookAnswer)
        class Missing:
            def ask(self, message, **kwargs):
                return "ok"


def test_a_misspelled_method_is_caught():
    """The error this is really for."""
    with pytest.raises(TypeError, match="on_message_sent"):
        @require(HookMessageSent)
        class Typo:
            def on_messages_sent(self, msg, **kwargs):
                pass


def test_a_non_callable_attribute_does_not_satisfy_a_hook():
    with pytest.raises(TypeError):
        @require(HookAsk)
        class NotAMethod:
            ask = "not callable"


def test_stacked_requires_accumulate():
    @require(HookAsk)
    @require(HookMessageSent)
    class Both:
        def ask(self, message, **kwargs):
            return "ok"

        def on_message_sent(self, msg, **kwargs):
            pass

    assert hooks_of(Both()) == frozenset({HookAsk, HookMessageSent})


def test_declaring_nothing_is_allowed_and_means_nothing_fires():
    class Quiet:
        def on_message_sent(self, msg, **kwargs):
            raise AssertionError("must never be called")

    quiet = Quiet()
    quiet.name = "quiet"
    session = ChatSession(connectors=[quiet])
    session.send_message("ola")  # would raise if the undeclared hook fired
    assert hooks_of(quiet) == frozenset()


# === @connector names ============================================================


def test_connector_names_the_class():
    @connector("weather")
    @require(HookAsk)
    class Weather:
        def ask(self, message, **kwargs):
            return "sol"

    assert Weather().name == "weather"
    assert name_of(Weather()) == "weather"


def test_an_instance_may_override_the_class_name():
    """Two links of the same kind to different agents."""
    @connector("agent")
    @require(HookAsk)
    class Agent:
        def __init__(self, name=None):
            if name is not None:
                self.name = name

        def ask(self, message, **kwargs):
            return "ok"

    session = ChatSession(connectors=[Agent("north"), Agent("south")])
    assert sorted(session.connectors) == ["north", "south"]


@pytest.mark.parametrize("bad", ["", "   ", None, 42])
def test_a_connector_needs_a_real_name(bad):
    with pytest.raises(ValueError):
        connector(bad)


def test_name_of_falls_back_to_the_class_name():
    class Anonymous:
        pass

    assert name_of(Anonymous()) == "Anonymous"


# === The shipped connectors declare themselves ===================================


def test_the_shipped_connectors_declare_only_the_outbound_role():
    for cls in (A2AConnector, OpenAIConnector):
        instance = cls.__new__(cls)  # no network in __init__
        assert declares(instance, HookAsk)
        assert not declares(instance, HookAnswer)


def test_lifecycle_is_optional_not_declared():
    """A connector holding nothing implements neither initialize nor shutdown."""
    @connector("bare")
    @require(HookAsk)
    class Bare:
        def ask(self, message, **kwargs):
            return "ok"

    session = ChatSession(connectors=[Bare()])
    session.close()
    assert session.ask_connector("bare", "ping") == "ok"
