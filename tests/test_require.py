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
from chatinho.chat_hooks import declares, hooks_of, name_of, options_of


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


# === One hook per require, with its own options ==================================


def test_require_takes_one_hook_and_says_what_to_do_instead():
    with pytest.raises(TypeError, match="stack decorators"):
        @require(HookAsk, HookMessageSent)
        class TwoAtOnce:
            def ask(self, message, **kwargs):
                return "ok"

            def on_message_sent(self, msg, **kwargs):
                pass


def test_require_rejects_something_that_is_not_a_hook():
    with pytest.raises(TypeError, match="takes a Hook"):
        @require("ask")
        class NotAHook:
            def ask(self, message, **kwargs):
                return "ok"


def test_each_hook_carries_its_own_options():
    @require(HookAsk, timeout=30)
    @require(HookAnswer, correlation="taskId")
    class Configured:
        def ask(self, message, **kwargs):
            return "ok"

        def answer(self, correlation_id, text):
            pass

    configured = Configured()
    assert options_of(configured, HookAsk) == {"timeout": 30}
    assert options_of(configured, HookAnswer) == {"correlation": "taskId"}


def test_a_hook_declared_without_options_has_none():
    @require(HookAsk)
    class Plain:
        def ask(self, message, **kwargs):
            return "ok"

    assert options_of(Plain(), HookAsk) == {}
    assert options_of(Plain(), HookMessageSent) == {}


def test_options_are_returned_as_a_copy():
    @require(HookAsk, timeout=30)
    class Configured:
        def ask(self, message, **kwargs):
            return "ok"

    configured = Configured()
    options_of(configured, HookAsk)["timeout"] = 999
    assert options_of(configured, HookAsk) == {"timeout": 30}


def test_declaring_the_same_hook_twice_merges_options():
    """Decorators apply bottom-up, so the highest one wins per key."""
    @require(HookAsk, timeout=99)
    @require(HookAsk, timeout=30, retries=2)
    class Twice:
        def ask(self, message, **kwargs):
            return "ok"

    assert options_of(Twice(), HookAsk) == {"timeout": 99, "retries": 2}


def test_options_do_not_leak_between_classes():
    @require(HookAsk, timeout=30)
    class First:
        def ask(self, message, **kwargs):
            return "ok"

    @require(HookAsk)
    class Second(First):
        pass

    assert options_of(First(), HookAsk) == {"timeout": 30}
    assert options_of(Second(), HookAsk) == {"timeout": 30}
    Second._hooks[HookAsk]["timeout"] = 1
    assert options_of(First(), HookAsk) == {"timeout": 30}


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
