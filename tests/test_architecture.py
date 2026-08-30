"""Architectural fitness tests.

The Dependency Rule is only worth anything if something enforces it. These
parse the core modules and fail if a UI import creeps back in — cheaper than
noticing months later that the session cannot run without a terminal.
"""

import ast
import pathlib

import pytest

SRC = pathlib.Path(__file__).resolve().parent.parent / "src" / "chatinho"

# Modules that must stay free of the delivery mechanism.
CORE_MODULES = [
    "chat_session.py",
    "chat_message.py",
    "chat_hooks.py",
    "commands/base.py",
    "backends/base.py",
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
