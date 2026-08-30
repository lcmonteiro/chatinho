"""Capabilities a connector declares, and the registry that dispatches to them.

A connector is a plain class. It says what it can do by declaring hooks, and
:func:`require` checks at class-definition time that it implements what it
declared — so a missing or misspelled method is an import error, not a silent
no-op at runtime.

    @connector("weather")
    @require(HookAsk)
    @require(HookMessageSent)
    class WeatherConnector:
        def ask(self, message, **kwargs): ...
        def on_message_sent(self, msg, **kwargs): ...

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
from typing import Any, Callable, Dict, FrozenSet, List, Optional, Tuple

logger = logging.getLogger(__name__)

# What a connector granted ``inbox`` calls to put a question in front of the
# user: ``inbox(text, correlation_id) -> message id``.
Inbox = Callable[[str, Optional[str]], str]


@dataclass(frozen=True)
class Hook:
    """One capability: the method it demands, and what the chat gives back.

    Attributes:
        name: How the hook reads in errors and logs.
        method: The method a connector declaring this hook must implement.
        grants: Attributes the session sets on the connector when it registers,
            for hooks whose capability needs something from the chat.
    """

    name   : str
    method : str
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

# === Events: what a connector wants to be told about ============================

HookMessageSent     = Hook("HookMessageSent",     "on_message_sent")
HookMessageReceived = Hook("HookMessageReceived", "on_message_received")
HookCommandExecuted = Hook("HookCommandExecuted", "on_command_executed")
HookConnectorAdded  = Hook("HookConnectorAdded",  "on_connector_added")
HookBackendSave     = Hook("HookBackendSave",     "on_backend_save")
HookBackendLoad     = Hook("HookBackendLoad",     "on_backend_load")

ALL_HOOKS: Tuple[Hook, ...] = (
    HookAsk,
    HookAnswer,
    HookMessageSent,
    HookMessageReceived,
    HookCommandExecuted,
    HookConnectorAdded,
    HookBackendSave,
    HookBackendLoad,
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
        if not callable(getattr(cls, hook.method, None)):
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
        for obj in self._by_hook.get(hook, []):
            try:
                getattr(obj, hook.method)(**payload)
            except Exception as exc:
                logger.error(
                    "Error in hook '%s' for connector %r: %s", hook, name_of(obj), exc,
                    exc_info=True,
                )


def name_of(obj: Any) -> str:
    """Returns a connector's name, falling back to its class name."""
    return str(getattr(obj, "name", type(obj).__name__))
