"""Capabilities a participant declares, and the registry that dispatches them.

A participant — a connector, a tool, or the presentation — is a plain class. It
says what it can do by declaring hooks, and :func:`require` checks at
class-definition time that it implements what it declared, so a missing or
misspelled method is an import error rather than a silent no-op at runtime.

There are three verbs and nothing else:

    say(text)          a message for everyone
    ask(to, text)      a message for one participant, awaiting its reply
    answer(msg, text)  the reply that ask is waiting on

and two ways of being told:

    on_say(msg)   someone spoke to everyone
    on_ask(msg)   someone asked *you*; return the answer, or answer() later

Everything is a coroutine and every participant has its own queue, so a slow
subsystem holds up nobody but itself.

    @connector("weather")
    @require(HookOnAsk)
    class WeatherConnector:
        async def on_ask(self, msg): return "sunny"

One hook per ``require``, stacked. Each declaration is its own line, so it has
somewhere to carry options that belong to that hook alone:

    @require(HookAsk, timeout=30)

Nothing here is inherited: no base class, no ``isinstance``.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, FrozenSet, List, Optional, Protocol, Tuple

from .chat_message import ChatMessage

logger = logging.getLogger(__name__)


class Say(Protocol):
    """Granted by ``HookSay``: a message for everyone."""

    async def __call__(self, text: str, *, reply_to: Optional[str] = None) -> str:
        """Adds *text* to the conversation and returns the new message's id."""
        ...


class Ask(Protocol):
    """Granted by ``HookAsk``: a message for one participant, and its reply."""

    async def __call__(self, to: int, text: str) -> str:
        """Asks participant *to* and waits for the answer it sends back."""
        ...


class Answer(Protocol):
    """Granted by ``HookOnAsk``: the reply an ask is waiting on.

    Only needed when the answer is not ready inline — a connector that has to
    reach a server returns None from ``on_ask`` and calls this once it knows.
    """

    async def __call__(self, msg: ChatMessage, text: str) -> str:
        """Answers *msg* with *text* and returns the reply's id."""
        ...


class Participants(Protocol):
    """Granted by ``HookParticipants``: who else is in the chat, by id."""

    def __call__(self) -> Dict[int, Any]:
        """Returns a copy of the roster, keyed by participant id."""
        ...


class LoadMessages(Protocol):
    """Granted by ``HookLoadMessages``: the history, by time or by index."""

    def __call__(
        self,
        *,
        since : Optional[datetime] = None,
        start : Optional[int] = None,
        limit : Optional[int] = None,
    ) -> List[ChatMessage]:
        """Returns the messages that survive the filters, oldest first."""
        ...


@dataclass(frozen=True)
class Hook:
    """One capability: the method it demands, and what the chat gives back.

    A hook can demand a method, grant an attribute, or both. A grant-only hook
    validates nothing — there is nothing on the class to check — but declaring
    it is still what tells the chat to hand the capability over.

    Attributes:
        name: How the hook reads in errors and logs.
        method: The method a class declaring this hook must implement, or None
            when the hook only grants.
        grants: Attributes the chat sets on the object when it registers.
    """

    name   : str
    method : Optional[str] = None
    grants : Tuple[str, ...] = ()

    def __str__(self) -> str:
        return self.name


# === The three verbs ============================================================

HookSay = Hook(
    name="HookSay",
    grants=("say",),
    # say(text, reply_to=None) -> id. Reaches every participant but the sender.
    # A reply to a say is another say: a broadcast is owed to nobody, so there
    # is no fourth verb for answering one.
)

HookAsk = Hook(
    name="HookAsk",
    grants=("ask",),
    # await ask(to, text) -> the answer. Addressed and owed: exactly one
    # participant, exactly one reply. ask(LOCAL, ...) asks the user.
)

HookOnSay = Hook(
    name="HookOnSay",
    method="on_say",
    # Someone spoke to everyone. Nothing is owed back.
)

HookOnAsk = Hook(
    name="HookOnAsk",
    method="on_ask",
    grants=("answer",),
    # Someone asked you. Return the answer to reply inline, or return None and
    # call self.answer(msg, text) once you know it — which is why being
    # askable is what grants the way to answer.
)

HookLoadMessages = Hook(
    name="HookLoadMessages",
    grants=("load_messages",),
    # The history, by time or by index. The only way to read it.
)

HookParticipants = Hook(
    name="HookParticipants",
    grants=("participants",),
    # Who else is here, by id. The roster's counterpart to load_messages: /help
    # lists it and the autocomplete popup matches against it, and neither can
    # be written without a way to see past its own class.
)

# === What a backend is for ======================================================

HookSave   = Hook("HookSave",   "save")
HookLoad   = Hook("HookLoad",   "load")
HookDelete = Hook("HookDelete", "delete")

ALL_HOOKS: Tuple[Hook, ...] = (
    HookSay,
    HookAsk,
    HookOnSay,
    HookOnAsk,
    HookLoadMessages,
    HookParticipants,
    HookSave,
    HookLoad,
    HookDelete,
)

# Lifecycle is not a hook: initialize() and shutdown() are optional and called
# when present. A participant holding nothing needs neither, and making it
# declare that it holds nothing is ceremony.


def connector(name: str) -> Callable[[type], type]:
    """Names a connector class.

    The name is how the chat addresses it — ``ask_connector("weather", ...)`` —
    and what a message carries as its ``origin``. An instance may override it by
    setting ``self.name``, for two links of the same kind to different agents.

    Args:
        name: The connector's name; must be a non-empty string.

    Returns:
        Callable: The class decorator.

    Raises:
        ValueError: If *name* is empty or not a string.
    """
    if not isinstance(name, str) or not name.strip():
        raise ValueError("A connector name must be a non-empty string, got %r" % (name,))

    def decorator(cls: type) -> type:
        cls.name = name  # type: ignore[attr-defined]
        return cls
    return decorator


def tool(name: str, description: str = "") -> Callable[[type], type]:
    """Names a tool and gives it the text the UI shows.

    A tool is a participant like any other, and a command is an ask addressed
    to one: typing ``/help`` asks the tool named "help". The name is what the
    user types after ``/``; the description is what the autocomplete popup and
    ``/help`` display beside it.

    Args:
        name: The command name, without the prefix; a non-empty string.
        description: One line shown beside the name.

    Returns:
        Callable: The class decorator.

    Raises:
        ValueError: If *name* is empty or not a string.
    """
    if not isinstance(name, str) or not name.strip():
        raise ValueError("A tool name must be a non-empty string, got %r" % (name,))

    def decorator(cls: type) -> type:
        cls.name = name                # type: ignore[attr-defined]
        cls.description = description  # type: ignore[attr-defined]
        return cls
    return decorator


def backend(name: str) -> Callable[[type], type]:
    """Names a backend class.

    The name only identifies the backend in logs — a chat has one — but naming
    it keeps the three roles reading the same way.

    Args:
        name: The backend's name; a non-empty string.

    Returns:
        Callable: The class decorator.

    Raises:
        ValueError: If *name* is empty or not a string.
    """
    if not isinstance(name, str) or not name.strip():
        raise ValueError("A backend name must be a non-empty string, got %r" % (name,))

    def decorator(cls: type) -> type:
        cls.name = name  # type: ignore[attr-defined]
        return cls
    return decorator


def require(hook: Hook, *extra: Any, **options: Any) -> Callable[[type], type]:
    """Declares one hook a connector implements, and checks that it does.

    Validation is presence and callability of the hook's method — the error
    this actually catches is a method left out or misspelled. It runs when the
    class is defined, so the failure lands at import rather than as a hook that
    silently never fires.

    One hook per call, stacked for more. Each declaration then owns its line
    and can carry options that belong to that hook alone::

        @require(HookAsk, timeout=30)
        @require(HookAnswer)
        class MyConnector: ...

    Declaring the same hook twice merges the options, later call winning per
    key — decorators apply bottom-up, so the one written highest wins.

    Args:
        hook: The capability the decorated class provides.
        *extra: Nothing; present only to reject ``require(HookA, HookB)`` with
            an error that says what to do instead.
        **options: Configuration for this hook, readable with :func:`options_of`.

    Returns:
        Callable: The class decorator.

    Raises:
        TypeError: If more than one hook is passed, if *hook* is not a Hook, or
            if the class does not implement the hook's method.
    """
    if extra:
        raise TypeError(
            "require() takes one hook; stack decorators to declare more, "
            "e.g. @require(%s) above @require(%s)" % (hook, extra[0])
        )
    if not isinstance(hook, Hook):
        raise TypeError("require() takes a Hook, got %r" % (hook,))

    def decorator(cls: type) -> type:
        if hook.method is not None and not callable(getattr(cls, hook.method, None)):
            raise TypeError(
                "%s declares %s but does not implement %s()"
                % (cls.__name__, hook.name, hook.method)
            )
        declared: Dict[Hook, Dict[str, Any]] = {
            key: dict(value) for key, value in getattr(cls, "_hooks", {}).items()
        }
        declared.setdefault(hook, {}).update(options)
        cls._hooks = declared  # type: ignore[attr-defined]
        return cls
    return decorator


def hooks_of(obj: Any) -> FrozenSet[Hook]:
    """Returns the hooks *obj*'s class declared, empty when it declared none."""
    return frozenset(getattr(obj, "_hooks", {}))


def options_of(obj: Any, hook: Hook) -> Dict[str, Any]:
    """Returns the options *obj* declared for *hook*, empty when it gave none.

    Args:
        obj: The connector.
        hook: The capability whose options to read.

    Returns:
        Dict[str, Any]: A copy, so a caller cannot edit the declaration.
    """
    return dict(getattr(obj, "_hooks", {}).get(hook, {}))


def declares(obj: Any, hook: Hook) -> bool:
    """Whether *obj* declared *hook*."""
    return hook in hooks_of(obj)


def name_of(obj: Any) -> str:
    """Returns a participant's visible name, falling back to its class name."""
    return str(getattr(obj, "name", type(obj).__name__))
