"""Hook system: connectors opt into chat events with ``@hook_point``.

The chat triggers every hook centrally through a :class:`HookRegistry`, so a
connector that declares no hook points is simply never called. Nothing here
touches Textual.
"""

import logging
from typing import Any, Callable, Dict, List

from .connectors import BaseConnector

logger = logging.getLogger(__name__)

HOOK_MESSAGE_SENT     : str = "message_sent"
HOOK_MESSAGE_RECEIVED : str = "message_received"
HOOK_COMMAND_EXECUTED : str = "command_executed"
HOOK_CONNECTOR_ADDED  : str = "connector_added"
HOOK_BACKEND_SAVE     : str = "backend_save"
HOOK_BACKEND_LOAD     : str = "backend_load"

# Hook name -> the connector method called when the hook fires.
HOOK_METHODS : Dict[str, str] = {
    HOOK_MESSAGE_SENT     : "on_message_sent",
    HOOK_MESSAGE_RECEIVED : "on_message_received",
    HOOK_COMMAND_EXECUTED : "on_command_executed",
    HOOK_CONNECTOR_ADDED  : "on_connector_added",
    HOOK_BACKEND_SAVE     : "on_backend_save",
    HOOK_BACKEND_LOAD     : "on_backend_load",
}

ALL_HOOKS = frozenset(HOOK_METHODS)


def hook_point(*event_names: str) -> Callable[[type], type]:
    """Declare which hook points a connector class handles.

    Only connectors decorated with the hook they care about are called; the
    matching ``on_*`` method receives that hook's payload as keyword arguments:

    ==========================  ======================  ==========================
    hook                        method                  payload
    ==========================  ======================  ==========================
    HOOK_MESSAGE_SENT           on_message_sent         msg
    HOOK_MESSAGE_RECEIVED       on_message_received     msg
    HOOK_COMMAND_EXECUTED       on_command_executed     command, result, error
    HOOK_CONNECTOR_ADDED        on_connector_added      connector
    HOOK_BACKEND_SAVE           on_backend_save         key, data
    HOOK_BACKEND_LOAD           on_backend_load         key, data
    ==========================  ======================  ==========================

    ``on_command_executed`` is called on both paths: on failure ``result`` is
    None and ``error`` carries the exception, on success ``error`` is None.
    Accept ``**kwargs`` so new payload keys do not break existing connectors.

    Usage:
        @hook_point(HOOK_MESSAGE_SENT, HOOK_MESSAGE_RECEIVED)
        class MyConnector(BaseConnector):
            def on_message_sent(self, msg, **kwargs): ...
            def on_message_received(self, msg, **kwargs): ...

    Args:
        *event_names: Hook constants the decorated class handles.

    Returns:
        Callable: The class decorator.
    """
    def decorator(cls: type) -> type:
        points = set(getattr(cls, "_hook_points", ()))
        points.update(event_names)
        cls._hook_points = points  # type: ignore[attr-defined]
        return cls
    return decorator


class HookRegistry:
    """Maps each hook to the connectors that declared it via ``@hook_point``."""

    def __init__(self) -> None:
        self._by_hook : Dict[str, List[BaseConnector]] = {hook: [] for hook in ALL_HOOKS}

    def register(self, connector: BaseConnector) -> None:
        """Registers *connector* for every hook point it declares.

        Args:
            connector: The connector to register.
        """
        for hook in getattr(connector, "_hook_points", ()):
            if hook in self._by_hook:
                self._by_hook[hook].append(connector)
            else:
                logger.warning("Connector %r declares unknown hook: %s", connector.name, hook)

    def unregister(self, connector: BaseConnector) -> None:
        """Removes *connector* from every hook, by identity.

        Args:
            connector: The connector to drop.
        """
        for registered in self._by_hook.values():
            registered[:] = [c for c in registered if c is not connector]

    def connectors_for(self, hook_name: str) -> List[BaseConnector]:
        """Returns the connectors registered for *hook_name*."""
        return list(self._by_hook.get(hook_name, []))

    def trigger(self, hook_name: str, **payload: Any) -> None:
        """Calls every connector registered for *hook_name*.

        A connector raising inside a hook is logged and skipped: one bad
        connector must not take the chat down.

        Args:
            hook_name: The hook constant to trigger.
            **payload: Passed to the connector's hook method as keyword arguments.
        """
        method_name = HOOK_METHODS.get(hook_name)
        if method_name is None:
            logger.warning("Unknown hook name: %s", hook_name)
            return

        for connector in self._by_hook.get(hook_name, []):
            method = getattr(connector, method_name, None)
            if method is None:
                logger.debug("Connector %r does not implement %s", connector.name, method_name)
                continue
            try:
                method(**payload)
            except Exception as exc:
                logger.error(
                    "Error in hook '%s' for connector %r: %s", hook_name, connector.name, exc,
                    exc_info=True,
                )
