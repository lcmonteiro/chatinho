"""Capabilities a connector declares, and the registry that dispatches to them.

A connector is a plain class. It says what it can do by declaring hooks, and
:func:`require` checks at class-definition time that it implements what it
declared — so a missing or misspelled method is an import error, not a silent
no-op at runtime.

    @connector("weather")
    @require(HookAsk)
    @require(HookReceiveMessage)
    class WeatherConnector:
        def ask(self, message, **kwargs): ...
        def on_receive_message(self, msg, **kwargs): ...

One hook per ``require``, stacked. Each declaration is its own line, so it has
somewhere to carry options that belong to that hook alone:

    @require(HookAsk, timeout=30)
    @require(HookAnswer, correlation="taskId")

Nothing here is inherited: no base class, no ``isinstance``. Direction and
event participation are declared the same way, because they are the same
question — what does this connector do?
"""

import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, FrozenSet, List, Optional, Protocol, Tuple

logger = logging.getLogger(__name__)

# What a connector granted ``inbox`` calls to put a question in front of the
# user: ``inbox(text, correlation_id) -> message id``.
Inbox = Callable[[str, Optional[str]], str]

class Say(Protocol):
    """What ``HookSay`` grants: writing into the conversation from outside.

    A protocol rather than a ``Callable`` alias because the granted call takes
    keyword arguments, and an alias cannot say so — it typed the grant more
    narrowly than the thing actually handed over. Annotate it on the class: the
    chat sets the attribute at registration, so without the annotation a type
    checker cannot see it.
    """

    def __call__(
        self,
        text : str,
        *,
        reply_to       : Optional[str] = None,
        origin         : Optional[str] = None,
        correlation_id : Optional[str] = None,
    ) -> str:
        """Adds *text* to the conversation and returns the new message's id."""
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


# === Roles: what a connector is for =============================================

HookAsk = Hook(
    name="HookAsk",
    method="ask",
    # The user asks, the far side answers. ask(message, **kwargs) -> answer.
)

HookAnswer = Hook(
    name="HookAnswer",
    method="answer",
    grants=("inbox",),
    # The far side can start the conversation: it calls self.inbox(text,
    # correlation_id) from its own listener, and the user's reply arrives as
    # answer(correlation_id, text).
)

# === The chat itself: what a plugin may do to the conversation ==================
#
# These five are the whole of the chat as a plugin sees it. Three are granted —
# the session sets them at registration and the plugin calls them — and two are
# demanded, so the session calls the plugin. Nothing else about the session is
# reachable: its methods are protected, and declaring a hook is the only door.

HookSendMessage = Hook(
    name="HookSendMessage",
    grants=("send_message",),
    # send_message(text, reply_to=None) -> message id. Enters the history as
    # sent by the user, and routes an answer back when it replies to a message
    # that arrived through a connector.
)

HookSendCommand = Hook(
    name="HookSendCommand",
    grants=("send_command",),
    # send_command(command) -> message id. The command line without the prefix.
)

HookLoadMessages = Hook(
    name="HookLoadMessages",
    grants=("load_messages",),
    # load_messages(since=None, start=None, limit=None) -> List[ChatMessage].
    # The history, by time or by index. The only way to read it.
)

HookReceiveMessage = Hook(
    name="HookReceiveMessage",
    method="on_receive_message",
    # A message entered the conversation. Called for every one of them, whoever
    # sent it, so a presentation can repaint on this alone.
)

HookReceiveCommand = Hook(
    name="HookReceiveCommand",
    method="on_receive_command",
    # A command entered the conversation, before it is dispatched.
)

# === Roles: what a command is for ===============================================

HookExecute = Hook(
    name="HookExecute",
    method="execute",
    # The user typed /name. execute(**kwargs) -> whatever should be displayed,
    # or None when the command wrote its own output through HookSay.
)

HookSay = Hook(
    name="HookSay",
    grants=("say",),
    # Grant-only: the chat hands over say(text), so a command can write into the
    # conversation as it works instead of returning one final string. Nothing to
    # validate — the class does not implement say, it receives it.
)

# === Roles: what a backend is for ===============================================

HookSave   = Hook("HookSave",   "save")
HookLoad   = Hook("HookLoad",   "load")
HookDelete = Hook("HookDelete", "delete")

# There is no "events" family. There were five — one per interesting moment —
# and every one of them was either derivable or unused: HookMessageSent carried
# nothing that HookReceiveMessage does not, since a message says whether it was
# sent by us, and it fired a second time for the same message; the other four
# had no consumer anywhere. The only things broadcast are the two notices about
# the conversation above.

ALL_HOOKS: Tuple[Hook, ...] = (
    HookSendMessage,
    HookSendCommand,
    HookLoadMessages,
    HookReceiveMessage,
    HookReceiveCommand,
    HookAsk,
    HookAnswer,
    HookExecute,
    HookSay,
    HookSave,
    HookLoad,
    HookDelete,
)

# Lifecycle is not a hook: initialize() and shutdown() are optional and called
# when present. A connector that holds nothing needs neither, and forcing it to
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


def command(name: str, description: str = "") -> Callable[[type], type]:
    """Names a command class and gives it the text the UI shows.

    The name is what the user types after ``/``; the description is what the
    autocomplete popup and ``/help`` display beside it.

    Args:
        name: The command name, without the prefix; a non-empty string.
        description: One line shown beside the name.

    Returns:
        Callable: The class decorator.

    Raises:
        ValueError: If *name* is empty or not a string.
    """
    if not isinstance(name, str) or not name.strip():
        raise ValueError("A command name must be a non-empty string, got %r" % (name,))

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


class HookRegistry:
    """Dispatches events to the connectors that declared them."""

    def __init__(self) -> None:
        self._by_hook : Dict[Hook, List[Any]] = {hook: [] for hook in ALL_HOOKS}

    def register(self, obj: Any) -> None:
        """Registers *obj* for every hook its class declared.

        Args:
            obj: The connector to register.
        """
        for hook in hooks_of(obj):
            if hook in self._by_hook:
                self._by_hook[hook].append(obj)
            else:
                logger.warning("Connector %r declares unknown hook: %s", name_of(obj), hook)

    def unregister(self, obj: Any) -> None:
        """Removes *obj* from every hook, by identity.

        Args:
            obj: The connector to drop.
        """
        for registered in self._by_hook.values():
            registered[:] = [c for c in registered if c is not obj]

    def connectors_for(self, hook: Hook) -> List[Any]:
        """Returns the connectors registered for *hook*."""
        return list(self._by_hook.get(hook, []))

    def trigger(self, hook: Hook, **payload: Any) -> None:
        """Calls every connector registered for *hook*.

        A connector raising inside a hook is logged and skipped: one bad
        connector must not take the chat down.

        Args:
            hook: The capability to trigger.
            **payload: Passed to the connector's method as keyword arguments.
        """
        method = hook.method
        if method is None:
            # A grant-only hook has nothing to call: it hands a capability over
            # at registration, it is not an event.
            logger.warning("Hook %s only grants; there is nothing to trigger", hook)
            return

        for obj in self._by_hook.get(hook, []):
            try:
                getattr(obj, method)(**payload)
            except Exception as exc:
                logger.error(
                    "Error in hook '%s' for connector %r: %s", hook, name_of(obj), exc,
                    exc_info=True,
                )


def name_of(obj: Any) -> str:
    """Returns a connector's name, falling back to its class name."""
    return str(getattr(obj, "name", type(obj).__name__))
