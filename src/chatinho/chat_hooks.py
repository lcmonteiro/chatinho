"""Capabilities a peer declares, and the registry that dispatches them.

A peer — a connector, a tool, or the presentation — is a plain class. It
says what it can do by declaring hooks, and :func:`require` checks at
class-definition time that it implements what it declared, so a missing or
misspelled method is an import error rather than a silent no-op at runtime.

There are three verbs and nothing else:

    say(text)          a message for everyone
    ask(to, text)      a message for one peer, awaiting its reply
    answer(msg, text)  the reply that ask is waiting on

and two ways of being told:

    listen(msg)   someone spoke to everyone
    answer(msg)   someone asked *you*; return the answer, or answer() later

Everything is a coroutine and every peer has its own queue, so a slow
subsystem holds up nobody but itself.

    @connector("weather")
    @require(HookAnswer)
    class WeatherConnector:
        async def answer(self, msg): return "sunny"

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
    """Granted by ``HookAsk``: a message for one peer, and its reply."""

    async def __call__(self, to: int, text: str) -> str:
        """Asks peer *to* and waits for the answer it sends back."""
        ...


class Peers(Protocol):
    """Granted by ``HookPeers``: who else is in the chat, by id."""

    def __call__(self) -> Dict[int, Any]:
        """Returns a copy of the roster, keyed by peer id."""
        ...


class Invoke(Protocol):
    """Granted by ``HookInvoke``: invoking a command and getting its result back.

    A command is not a peer — it has no id, no queue and receives nothing. It
    runs, it may write into the conversation, and it answers whoever ran it.
    """

    async def __call__(self, name: str, args: str = "") -> Optional[str]:
        """Runs the command called *name* and returns what it answered.

        Returns None when there is no such command, or when the command chose
        to write its output rather than answer with it.
        """
        ...


class Context(Protocol):
    """Granted by ``HookContext``: the conversation so far, at any depth.

    One interface over two tiers. The recent turns live in the session; older
    ones live in the backend and are recalled into it at ``start()``. Whoever
    asks never learns which tier a message came from — that is the point.
    """

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
#
# Each verb is a pair: the word you call, and the word the other side writes.
#
#     say     -> listen        a message for everyone
#     ask     -> answer        a message for one peer, and its reply
#     invoke  -> execute       a command run by name
#
# The pairs are not decoration, and no verb keeps an `on_` prefix. `say` is
# something you do; `listen` is what the session calls on you when someone did.
#
# Everything below is either a grant (what you may do, set on you at attach) or
# a demand (what you must write, called by the session) — never both, and no
# hook is both. A grant arrives by setattr and would silently clobber a method
# of the same name, which is why `answer` can be the demanded method only now
# that it is not also a grant.

HookSay = Hook(
    name="HookSay",
    grants=("say",),
    # say(text, reply_to=None) -> id. Reaches every peer but the sender.
    # A reply to a say is another say: a broadcast is owed to nobody, so there
    # is no fourth verb for answering one.
)

HookAsk = Hook(
    name="HookAsk",
    grants=("ask",),
    # await ask(to, text) -> the answer. Addressed and owed: exactly one
    # peer, exactly one reply. ask(LOCAL, ...) asks the user.
)

HookListen = Hook(
    name="HookListen",
    method="listen",
    # async listen(msg). Someone spoke to everyone and you were in the room.
    # Nothing is owed back: a reply to a say is another say.
)

HookAnswer = Hook(
    name="HookAnswer",
    method="answer",
    # async answer(msg) -> str | None. Someone asked you; what you return is
    # the reply, and the session posts it in your name.
    #
    # Return None when the answer is not yours to invent yet — a terminal
    # waiting on a person, a connector waiting on a server. The ask stays
    # waiting, and whatever you say later with reply_to=msg.id resolves it.
    # That is the same door, not a second one: there is no separate grant for
    # answering late, and there never needed to be.
)

HookInvoke = Hook(
    name="HookInvoke",
    grants=("invoke",),
    # await run(name, args) -> the command's answer, or None. A peer that may
    # invoke commands. The answer comes back to the peer that ran it; nothing
    # about the invocation enters the conversation.
)

HookExecute = Hook(
    name="HookExecute",
    method="execute",
    # async execute(args, **kwargs) -> str | None. What a command is. It is not
    # a peer: no id, no queue, nothing addressed to it. Declare HookSay too and
    # it can write as it works; return a string and that goes to whoever ran it.
)

HookContext = Hook(
    name="HookContext",
    grants=("context",),
    # context(since=, start=, limit=) -> the conversation so far, by time or by
    # index. The only way to read it, and it spans both tiers: what the session
    # holds and what the backend recalled into it.
)

HookPeers = Hook(
    name="HookPeers",
    grants=("peers",),
    # Who else is here, by id. The roster's counterpart to load_messages: /help
    # lists it and the autocomplete popup matches against it, and neither can
    # be written without a way to see past its own class.
)

# === Hearing everything, and holding it =========================================
#
# `overhear` is not `listen` with a wider net, and the names say which is which:
# you listen to what was said to the room, and you overhear what was not said
# to you at all. A backend, an audit log and a metrics counter want the second.

HookOverhear = Hook(
    name="HookOverhear",
    method="overhear",
    # async overhear(msg). Every message that crosses the session, whoever said
    # it and whoever it was for — not just the broadcasts listen brings, nor
    # only what was addressed to you. Nothing is owed back.
    #
    # You still never hear yourself. That is what stops a listener that speaks
    # from answering its own words forever, and it is the same rule as say.
)

HookLoad = Hook(
    name="HookLoad",
    method="load",
    # async load(since=, limit=) -> List[ChatMessage]. The older context, read
    # back at start(). A peer that overhears and loads *is* the archive:
    # it heard the conversation, and it gives it back.
)

HookForget = Hook(
    name="HookForget",
    method="forget",
    # async forget(before=) -> int. How much of what was held gets dropped.
)

ALL_HOOKS: Tuple[Hook, ...] = (
    HookSay,
    HookListen,
    HookAsk,
    HookAnswer,
    HookInvoke,
    HookExecute,
    HookContext,
    HookPeers,
    HookOverhear,
    HookLoad,
    HookForget,
)

# Lifecycle is not a hook: initialize() and shutdown() are optional and called
# when present. A peer holding nothing needs neither, and making it
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

    A tool is a peer like any other, and a command is an ask addressed
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
    """Returns a peer's visible name, falling back to its class name."""
    return str(getattr(obj, "name", type(obj).__name__))
