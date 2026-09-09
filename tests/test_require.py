"""Tests for @require, @connector, @tool and @backend.

A peer is a plain class. ``require`` checks at class-definition time
that it implements what it declared, so a missing or misspelled method is an
import error rather than a hook that silently never fires.
"""

import pytest

from chatinho import (
    HookAsk,
    HookContext,
    HookAnswer,
    HookListen,
    HookSay,
    backend,
    connector,
    declares,
    hooks_of,
    name_of,
    options_of,
    require,
    tool,
)
from conftest import driven


# === Validation at class-definition time ========================================


def test_a_declared_method_that_exists_is_accepted():
    @require(HookListen)
    class Fine:
        async def listen(self, msg):
            pass

    assert declares(Fine(), HookListen)


def test_a_declared_method_that_is_missing_is_an_import_error():
    with pytest.raises(TypeError, match="does not implement listen"):

        @require(HookListen)
        class Missing:
            pass


def test_a_misspelled_method_is_caught_the_same_way():
    with pytest.raises(TypeError, match="answer"):

        @require(HookAnswer)
        class Typo:
            async def answers(self, msg):    # the typo is the point
                pass


def test_a_grant_only_hook_validates_nothing():
    """HookSay hands say() over; there is nothing on the class to check."""

    @require(HookSay)
    class Silent:
        pass

    assert declares(Silent(), HookSay)


# === Stacking ===================================================================


def test_hooks_stack_and_are_all_remembered():
    @require(HookListen)
    @require(HookAsk)
    class Both:
        async def listen(self, msg):
            pass

    assert hooks_of(Both()) == frozenset({HookAsk, HookListen})


def test_two_hooks_in_one_require_says_to_stack_instead():
    with pytest.raises(TypeError, match="stack decorators"):

        @require(HookAsk, HookListen)
        class Wrong:
            async def listen(self, msg):
                pass


def test_require_refuses_something_that_is_not_a_hook():
    with pytest.raises(TypeError, match="takes a Hook"):

        @require("HookAsk")
        class Wrong:
            pass


def test_declaring_nothing_is_allowed_and_means_nothing_fires():
    class Quiet:
        name = "quiet"

        async def listen(self, msg):
            raise AssertionError("must never be called")

    assert hooks_of(Quiet()) == frozenset()


async def test_an_undeclared_hook_is_never_dispatched_to():
    """The methods are there; without the declaration nothing reaches them."""

    class Quiet:
        name = "quiet"

        def __init__(self):
            self.heard = []

        async def listen(self, msg):
            self.heard.append(msg)

    session, view = await driven()
    quiet = Quiet()
    session.attach(quiet)
    await session.start()
    await view.say("ola")
    assert quiet.heard == []
    await session.close()


# === Options ====================================================================


def test_options_ride_along_with_the_hook_that_owns_them():
    @require(HookAsk, timeout=30)
    @require(HookListen, batch=5)
    class Tuned:
        async def listen(self, msg):
            pass

    tuned = Tuned()
    assert options_of(tuned, HookAsk) == {"timeout": 30}
    assert options_of(tuned, HookListen) == {"batch": 5}
    assert options_of(tuned, HookContext) == {}


def test_options_of_hands_back_a_copy():
    @require(HookAsk, timeout=30)
    class Tuned:
        pass

    tuned = Tuned()
    options_of(tuned, HookAsk)["timeout"] = 1
    assert options_of(tuned, HookAsk) == {"timeout": 30}


def test_declaring_the_same_hook_twice_merges_the_options():
    """Decorators apply bottom-up, so the one written highest wins."""

    @require(HookAsk, timeout=1)
    @require(HookAsk, timeout=99, retries=2)
    class Tuned:
        pass

    assert options_of(Tuned(), HookAsk) == {"timeout": 1, "retries": 2}


def test_a_subclass_does_not_write_into_its_parents_declaration():
    @require(HookAsk)
    class Parent:
        pass

    @require(HookListen)
    class Child(Parent):
        async def listen(self, msg):
            pass

    assert hooks_of(Parent()) == frozenset({HookAsk})
    assert hooks_of(Child()) == frozenset({HookAsk, HookListen})


# === Names ======================================================================


def test_connector_names_the_class_and_an_instance_may_override_it():
    @connector("weather")
    class Weather:
        pass

    assert name_of(Weather()) == "weather"
    other = Weather()
    other.name = "weather-eu"
    assert name_of(other) == "weather-eu"


def test_a_tool_carries_the_text_the_popup_shows():
    @tool("deploy", "Ship it")
    class Deploy:
        pass

    assert (name_of(Deploy()), Deploy().description) == ("deploy", "Ship it")


def test_an_undecorated_class_falls_back_to_its_class_name():
    class Anonymous:
        pass

    assert name_of(Anonymous()) == "Anonymous"


@pytest.mark.parametrize("naming", [connector, tool, backend])
@pytest.mark.parametrize("bad", ["", "   ", None, 7])
def test_an_empty_name_is_refused(naming, bad):
    with pytest.raises(ValueError, match="non-empty string"):
        naming(bad)
