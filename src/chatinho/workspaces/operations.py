"""
What can be done in a workspace, declared one method at a time.

An operation is an ``async def`` on :class:`~chatinho.workspaces.views.WorkspaceView`
or :class:`~chatinho.workspaces.views.Workspace` marked with :func:`operation`.
Every consumer — an agent's tools, ``/ws`` — takes the set from
:func:`operations_of`, so adding one is writing one method::

    class MyView(WorkspaceView):
        @operation("List the Python symbols defined in a file")
        async def symbols(self, path: str) -> List[str]: ...

A writing operation says ``writes=True``. It then runs under its workspace's
lock, taken here rather than by each operation, so none has to remember to.
"""

import functools
import inspect
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Tuple

#: Where :func:`operation` leaves its declaration on the function.
_DECLARED = "_chatinho_operation"


@dataclass(frozen=True)
class Operation:
    """
    One operation of a workspace, as its class declares it.

    Attributes:
        name: The method's name, which is also the operation's.
        description: One line saying what it does; an agent's tool shows it.
        writes: Whether it changes the workspace, and so runs under its lock.
        parameters: The method's parameters, ``self`` left out, in order.
    """

    name        : str
    description : str
    writes      : bool
    parameters  : Tuple[inspect.Parameter, ...]


def operation(description: str, writes: bool = False) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Declares a method an operation of its workspace.

    Args:
        description: One line saying what it does.
        writes: Whether it changes the workspace. A writing operation runs under
            the workspace's lock, one at a time, in the order they were called.

    Returns:
        Callable: The method decorator.

    Raises:
        TypeError: When the method is not a coroutine function — raised where
            the class is defined, not when the operation is first called.
    """
    def decorator(method: Callable[..., Any]) -> Callable[..., Any]:
        if not inspect.iscoroutinefunction(method):
            raise TypeError("Operation %s must be an async def" % getattr(method, "__qualname__", method))

        declared : Callable[..., Any] = method
        if writes:
            @functools.wraps(method)
            async def locked(self: Any, *args: Any, **kwargs: Any) -> Any:
                async with self.tree.lock:
                    return await method(self, *args, **kwargs)
            declared = locked
        parameters = tuple(inspect.signature(method).parameters.values())[1:]
        setattr(declared, _DECLARED, Operation(method.__name__, description, writes, parameters))
        return declared
    return decorator


def operations_of(cls: Any) -> List[Operation]:
    """
    Returns the operations a view or workspace class declares, inherited ones included.

    In definition order, base classes first. A subclass that redefines an
    operation keeps its place and takes its new declaration.

    Args:
        cls: The class, or an instance of it.

    Returns:
        List[Operation]: Its operations.
    """
    klass = cls if isinstance(cls, type) else type(cls)
    found : Dict[str, Operation] = {}
    for base in reversed(klass.__mro__):
        for name, member in vars(base).items():
            declared = getattr(member, _DECLARED, None)
            if isinstance(declared, Operation):
                found[name] = declared
            elif name in found and callable(member):
                del found[name]          # redefined without the decorator: no longer an operation
    return list(found.values())
