"""Architectural fitness tests.

The Dependency Rule is only worth anything if something enforces it. These
parse the core modules and fail if a UI import creeps back in — cheaper than
noticing months later that the session cannot run without a terminal.
"""

import ast
import importlib
import inspect
import pathlib

import chatinho
from chatinho import Hook

import pytest

SRC = pathlib.Path(__file__).resolve().parent.parent / "src" / "chatinho"

# Modules that must stay free of the delivery mechanism.
CORE_MODULES = [
    "chat_session.py",
    "chat_message.py",
    "chat_hooks.py",
]

# Modules that are allowed to know about Textual: the presentation layer.
PRESENTATION_MODULES = [
    "chat_app.py",
    "chat_log.py",
    "chat_input.py",
]


def imported_roots(path: pathlib.Path) -> set:
    """Returns the top-level package names *path* imports."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                roots.add(node.module.split(".")[0])
    return roots


@pytest.mark.parametrize("module", CORE_MODULES)
def test_core_modules_do_not_import_the_ui_framework(module):
    roots = imported_roots(SRC / module)
    assert "textual" not in roots, f"{module} must not depend on Textual"


@pytest.mark.parametrize("module", CORE_MODULES)
def test_core_modules_do_not_import_adapter_libraries(module):
    """Policy must not reach out to a concrete transport or database driver."""
    roots = imported_roots(SRC / module)
    forbidden = roots & {"openai", "sqlalchemy", "requests", "httpx"}
    assert not forbidden, f"{module} must not depend on {sorted(forbidden)}"


def test_the_presentation_layer_is_the_only_place_that_knows_textual():
    with_textual = [
        path.relative_to(SRC).as_posix()
        for path in sorted(SRC.rglob("*.py"))
        if "textual" in imported_roots(path)
    ]
    assert with_textual == sorted(PRESENTATION_MODULES)


def test_the_session_does_not_depend_on_the_app():
    roots = imported_roots(SRC / "chat_session.py")
    assert "chat_app" not in roots
    tree = ast.parse((SRC / "chat_session.py").read_text(encoding="utf-8"))
    relative = {
        node.module for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.level > 0 and node.module
    }
    assert "chat_app" not in relative, "the session must never import its presentation"
    assert "chat_log" not in relative
    assert "chat_input" not in relative


# === Names we must not take from Textual ========================================


def _assigned_attributes(path: str, class_name: str) -> set:
    """Returns the ``self.X`` names a class assigns anywhere in its body."""
    tree = ast.parse(pathlib.Path(path).read_text())
    cls  = next(n for n in ast.walk(tree)
                if isinstance(n, ast.ClassDef) and n.name == class_name)
    names = set()
    for node in ast.walk(cls):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (isinstance(target, ast.Attribute)
                        and isinstance(target.value, ast.Name)
                        and target.value.id == "self"):
                    names.add(target.attr)
    return names


@pytest.mark.parametrize(
    "module, class_name, base",
    [
        ("src/chatinho/chat_app.py",   "_Chat",              "textual.app:App"),
        ("src/chatinho/chat_log.py",   "ChatLog",            "textual.containers:Container"),
        ("src/chatinho/chat_input.py", "CommandInput",       "textual.widgets:Input"),
        ("src/chatinho/chat_input.py", "CommandSuggestions", "textual.widgets:OptionList"),
    ],
)
def test_a_grant_never_shadows_a_textual_method(module, class_name, base):
    """A grant arrives by setattr, so the assignment check above cannot see it.

    This is not hypothetical: `_Chat` was granted `run`, which is Textual's own
    `App.run()` — the documented way to start the app. mypy caught that one
    because the class annotates its grants; a class that did not annotate them
    would have shipped it.
    """
    where, attribute = base.split(":")
    parent = getattr(importlib.import_module(where), attribute)
    granted = {name
               for hook in _declared_hooks(module, class_name)
               for name in getattr(chatinho, hook, Hook("?")).grants}
    taken = sorted(n for n in granted if inspect.isroutine(getattr(parent, n, None)))
    assert taken == [], "%s is granted %s, which is a method on %s" % (class_name, taken, attribute)


def _declared_hooks(path: str, class_name: str) -> set:
    """Returns the hook names a class declares with @require."""
    tree = ast.parse(pathlib.Path(path).read_text())
    cls  = next(n for n in ast.walk(tree)
                if isinstance(n, ast.ClassDef) and n.name == class_name)
    return {d.args[0].id
            for d in cls.decorator_list
            if isinstance(d, ast.Call) and getattr(d.func, "id", None) == "require"
            and d.args and isinstance(d.args[0], ast.Name)}


@pytest.mark.parametrize(
    "module, class_name, base",
    [
        ("src/chatinho/chat_app.py",   "_Chat",              "textual.app:App"),
        ("src/chatinho/chat_log.py",   "ChatLog",            "textual.containers:Container"),
        ("src/chatinho/chat_input.py", "CommandInput",       "textual.widgets:Input"),
        ("src/chatinho/chat_input.py", "CommandSuggestions", "textual.widgets:OptionList"),
    ],
)
def test_we_never_shadow_a_textual_method(module, class_name, base):
    """Replacing one of Textual's own methods with data breaks it in silence.

    Setting a Textual *property* is ordinary use — ``self.title``, ``self.value``
    — so only methods are checked. The one that bit was ``_context``:
    MessagePump's own context manager, shadowed by a granted reader of the same
    name, which hung the widget's message loop with no error at all until a
    test timed out. ``id`` at least raised.
    """
    where, attribute = base.split(":")
    parent = getattr(importlib.import_module(where), attribute)
    taken  = sorted(
        name for name in _assigned_attributes(module, class_name)
        if inspect.isroutine(getattr(parent, name, None))
    )
    assert taken == [], "%s assigns %s, which is a method on %s" % (class_name, taken, attribute)
