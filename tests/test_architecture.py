"""
Architectural fitness tests.

The Dependency Rule is only worth anything if something enforces it. These
parse the core modules and fail if a UI import creeps back in — cheaper than
noticing months later that the session cannot run without a terminal.
"""

import ast
import importlib
import inspect
import pathlib
import subprocess
import sys
import tomllib

import chatinho
from chatinho import Hook

import pytest

SRC = pathlib.Path(__file__).resolve().parent.parent / "src" / "chatinho"

# Modules that must stay free of the delivery mechanism.
CORE_MODULES = [
    "session.py",
    "message.py",
    "hooks.py",
    "query.py",
    "routers/simple.py",
]

# The package that is allowed to know about Textual: the terminal frontend.
PRESENTATION_PACKAGE = "frontends/chat/"


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
    forbidden = roots & {"openai", "sqlalchemy", "requests", "httpx", "mcp", "mcp_types", "fastmcp"}
    assert not forbidden, f"{module} must not depend on {sorted(forbidden)}"


def test_the_presentation_layer_is_the_only_place_that_knows_textual():
    with_textual = [
        path.relative_to(SRC).as_posix()
        for path in sorted(SRC.rglob("*.py"))
        if "textual" in imported_roots(path)
    ]
    outside = [path for path in with_textual if not path.startswith(PRESENTATION_PACKAGE)]
    assert outside == [], "only %s may import Textual: %s" % (PRESENTATION_PACKAGE, outside)
    assert PRESENTATION_PACKAGE + "__init__.py" in with_textual


@pytest.mark.parametrize("module", CORE_MODULES)
def test_the_core_does_not_depend_on_a_frontend_or_the_builders(module):
    tree = ast.parse((SRC / module).read_text(encoding="utf-8"))
    relative = {
        node.module.split(".")[0] for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.level > 0 and node.module
    }
    assert "frontends" not in relative, "%s must never import a frontend" % module
    assert "builder" not in relative, "%s must never import the builders" % module


#: What a workspace is, and the provider that makes them: both in the core.
WORKSPACE_PACKAGES = ("shared_parts/workspace", "workspaces")


def test_workspaces_use_only_the_standard_library():
    """Workspaces are in the core, so `import chatinho` must not need anything to use one."""
    found = {}
    for package in WORKSPACE_PACKAGES:
        for path in sorted((SRC / package).rglob("*.py")):
            outside = imported_roots(path) - set(sys.stdlib_module_names) - {"chatinho"}
            if outside:
                found[path.relative_to(SRC).as_posix()] = sorted(outside)
    assert found == {}, "the workspaces must import only the standard library: %s" % found


# === The four layers ============================================================

#: The session and the definition of the hooks. Imports nothing of chatinho but itself.
FRAMEWORK = {"session", "hooks", "message", "query"}

#: The parts more than one specialization uses, a package per domain. Imports the framework,
#: and nothing but the standard library.
SHARED = "shared_parts"

#: What a specialization is built from. Imports the framework and the shared code.
KITS = "shared_kits"

#: What implements the hooks. Imports everything above, never one another.
SPECIALIZATIONS = {"connectors", "frontends", "backends", "commands", "routers", "workspaces"}

#: What puts the three together, and so may import all of them.
ASSEMBLY = {"__init__.py", "builder.py"}


def imported_parts(path: pathlib.Path) -> set:
    """Returns the top-level parts of chatinho that *path* imports: ``hooks``, ``connectors``…"""
    package = ("chatinho",) + path.relative_to(SRC).parts[:-1]
    parts   = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            targets = [alias.name.split(".") for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            base   = package[:len(package) - node.level + 1] if node.level else ()
            module = tuple(node.module.split(".")) if node.module else ()
            # ``from . import x`` names the module in the alias, not in ``module``.
            targets = [list(base + module + (alias.name,)) for alias in node.names]
        else:
            continue
        parts.update(target[1] for target in targets if target[0] == "chatinho" and len(target) > 1)
    return parts


def layer_files(top: str) -> list:
    """Returns every module of the top-level part *top*, a file or a package."""
    single = SRC / (top + ".py")
    return [single] if single.exists() else sorted((SRC / top).rglob("*.py"))


def test_every_part_of_the_package_belongs_to_a_layer():
    """A new file or folder at the root has to be given a layer, or the rules below skip it."""
    tops = {path.name for path in SRC.iterdir() if path.suffix == ".py" or (path / "__init__.py").exists()}
    known = {name + ".py" for name in FRAMEWORK} | {SHARED, KITS} | SPECIALIZATIONS | ASSEMBLY
    assert tops == known


@pytest.mark.parametrize("module", sorted(FRAMEWORK))
def test_the_framework_imports_only_the_framework(module):
    outside = imported_parts(SRC / (module + ".py")) - FRAMEWORK
    assert outside == set(), "%s.py is the framework and must not import %s" % (module, sorted(outside))


def shared_domain(path: pathlib.Path) -> str:
    """Returns the domain of the shared code *path* is in: ``keys``, ``workspace``, ``memory``…"""
    return path.relative_to(SRC / SHARED).parts[0].removesuffix(".py")


def test_the_shared_code_imports_only_the_framework():
    """Not a kit, not a specialization, and not another domain of its own."""
    found = {}
    for path in layer_files(SHARED):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        outside = imported_parts(path) - FRAMEWORK - {SHARED}
        domains = imported_domains(path, tree) - {shared_domain(path)}
        if outside or domains:
            found[path.relative_to(SRC).as_posix()] = sorted(outside | domains)
    assert found == {}, "shared code must import only the framework: %s" % found


def imported_domains(path: pathlib.Path, tree: ast.AST) -> set:
    """Returns the domains of the shared code that *path*, itself shared code, imports."""
    package = ("chatinho",) + path.relative_to(SRC).parts[:-1]
    domains = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        base   = package[:len(package) - node.level + 1] if node.level else ()
        module = tuple(node.module.split(".")) if node.module else ()
        for alias in node.names:
            target = base + module + (alias.name,)
            if target[:2] == ("chatinho", SHARED) and len(target) > 2:
                domains.add(target[2])
    return domains - {"__init__"}


#: What the shared code imports inside a function, behind an extra of its own: the OS keychain.
SHARED_ON_FIRST_USE = {"keyring"}


def test_the_shared_code_uses_only_the_standard_library():
    found = {}
    for path in layer_files(SHARED):
        outside = imported_roots(path) - set(sys.stdlib_module_names) - {"chatinho"} - SHARED_ON_FIRST_USE
        if outside:
            found[path.relative_to(SRC).as_posix()] = sorted(outside)
    assert found == {}, "shared code must import only the standard library: %s" % found


def test_a_kit_imports_no_specialization():
    found = {}
    for path in layer_files(KITS):
        above = imported_parts(path) & (SPECIALIZATIONS | {"builder"})
        if above:
            found[path.relative_to(SRC).as_posix()] = sorted(above)
    assert found == {}, "a kit must not import what is built from it: %s" % found


@pytest.mark.parametrize("specialization", sorted(SPECIALIZATIONS))
def test_a_specialization_imports_no_other(specialization):
    found = {}
    for path in layer_files(specialization):
        others = imported_parts(path) & ((SPECIALIZATIONS - {specialization}) | {"builder"})
        if others:
            found[path.relative_to(SRC).as_posix()] = sorted(others)
    assert found == {}, "%s must not import another specialization: %s" % (specialization, found)


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
        ("src/chatinho/frontends/chat/__init__.py", "ChatFrontend",       "textual.app:App"),
        ("src/chatinho/frontends/chat/messages.py", "ChatLog",            "textual.containers:Container"),
        ("src/chatinho/frontends/chat/composer.py", "CommandInput",       "textual.widgets:Input"),
        ("src/chatinho/frontends/chat/composer.py", "CommandSuggestions", "textual.widgets:OptionList"),
    ],
)
def test_a_grant_never_shadows_a_textual_method(module, class_name, base):
    """
    A grant arrives by setattr, so the assignment check above cannot see it.

    This is not hypothetical: `ChatFrontend` was granted `run`, which is Textual's own
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
        ("src/chatinho/frontends/chat/__init__.py", "ChatFrontend",       "textual.app:App"),
        ("src/chatinho/frontends/chat/messages.py", "ChatLog",            "textual.containers:Container"),
        ("src/chatinho/frontends/chat/composer.py", "CommandInput",       "textual.widgets:Input"),
        ("src/chatinho/frontends/chat/composer.py", "CommandSuggestions", "textual.widgets:OptionList"),
    ],
)
def test_we_never_shadow_a_textual_method(module, class_name, base):
    """
    Replacing one of Textual's own methods with data breaks it in silence.

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


# === The spec is a boundary too =================================================

DOCS = pathlib.Path(__file__).resolve().parent.parent / "docs"


def _spec_table():
    """The hooks named in docs/SPEC.md's summary table, as {hook: (demands, grants)}."""
    rows = {}
    for line in (DOCS / "SPEC.md").read_text(encoding="utf-8").splitlines():
        if not line.startswith("| [`Hook"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        name  = cells[0].split("`")[1]
        rows[name] = (cells[1].strip("`"), cells[2].strip("`"))
    return rows


def test_the_spec_lists_every_hook_and_gets_each_one_right():
    """
    A spec nothing checks is a spec that rots.

    docs/SPEC.md is the reference for the hooks, so its summary table has to say
    what the constants actually say: same set, same demanded method, same
    grants. Adding a hook without documenting it fails here.
    """
    documented = _spec_table()
    declared   = {
        h.name: (h.method or "—", ", ".join(h.grants) or "—")
        for h in (getattr(chatinho, n) for n in chatinho.__all__ if n.startswith("Hook") and n != "Hook")
    }
    assert documented == declared


def test_the_spec_has_a_section_for_every_hook():
    """Every hook in the table gets its own section, with an example."""
    spec    = (DOCS / "SPEC.md").read_text(encoding="utf-8")
    missing = [name for name in _spec_table() if "### %s\n" % name not in spec]
    assert missing == [], "docs/SPEC.md has no section for %s" % missing


# === Importable without the batteries ===========================================

ROOT = pathlib.Path(__file__).resolve().parent.parent

_WITHOUT_THE_EXTRAS = """
import builtins, sys
real = builtins.__import__
def blocked(name, *a, **k):
    if name.split(".")[0] in {"textual", "openai", "sqlalchemy", "requests", "mcp", "mcp_types", "fastmcp",
                                 "deepagents"}:
        raise ImportError("No module named %r" % name)
    return real(name, *a, **k)
builtins.__import__ = blocked

import chatinho
from chatinho import ChatSession, HelpCommand, TestCommand, SimpleRouter, ChatMessage, require, HookListen
print("core-ok")
for name in sorted(chatinho._BEHIND_AN_EXTRA):
    try:
        getattr(chatinho, name)
    except ImportError as exc:
        print(name, "->", "chatinho[" in str(exc))
"""


def test_the_core_imports_with_none_of_the_batteries_installed():
    """
    ``import chatinho`` must not need a terminal, an HTTP client and an ORM.

    A project that embeds the session in a service installs the package and
    nothing else; the names that need an extra are resolved on first use
    (PEP 562) and report the extra by name when it is missing. Run in a fresh
    interpreter, because the point is what happens at import.
    """
    done = subprocess.run(
        [sys.executable, "-c", _WITHOUT_THE_EXTRAS],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    assert done.returncode == 0, done.stderr
    lines = done.stdout.split()
    assert "core-ok" in done.stdout, done.stdout
    assert lines.count("True") == len(chatinho._BEHIND_AN_EXTRA), \
        "an extra is not named in its own error:\n%s" % done.stdout


def test_the_declared_extras_are_the_ones_the_package_asks_for():
    """pyproject's extras and the lazy table have to agree, or a name lies."""
    declared = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert declared["project"]["dependencies"] == [], "the core must install nothing"

    extras = declared["project"]["optional-dependencies"]
    needed = {pair for _, pairs in chatinho._BEHIND_AN_EXTRA.values() for pair in pairs}
    named  = {extra for extra, _ in needed}
    assert named <= set(extras), "chatinho names extras that pyproject does not declare"

    for extra, needs in needed:
        assert any(spec.startswith(needs) for spec in extras[extra]), \
            "extra %r does not install %r" % (extra, needs)
        assert any(spec.startswith(needs) for spec in extras["all"]), \
            "chatinho[all] does not install %r" % needs



def test_the_lazy_names_are_visible_to_a_type_checker():
    """
    PEP 562 hands a type checker ``Any``; the TYPE_CHECKING block undoes it.

    The package ships ``py.typed``, so a consumer's mypy is meant to see real
    signatures. Resolving the four battery names through ``__getattr__`` erased
    exactly those four — measured with ``reveal_type``, which said ``Any``.
    Importing them under ``if TYPE_CHECKING`` restores the annotations without
    importing anything at run time, and this fails if one is left out.
    """
    tree = ast.parse((SRC / "__init__.py").read_text(encoding="utf-8"))
    guarded = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.If) and getattr(node.test, "id", None) == "TYPE_CHECKING"
        for stmt in ast.walk(node)
        if isinstance(stmt, ast.ImportFrom)
        for alias in stmt.names
    }
    assert guarded == set(chatinho._BEHIND_AN_EXTRA), (
        "every lazily resolved name needs a TYPE_CHECKING import, or it is Any "
        "to everyone who installs this"
    )


_COUNTS = ("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
           "sixteen seventeen eighteen nineteen twenty").split()


def test_the_package_description_counts_the_hooks():
    """The description said eighteen while there were fourteen, and nothing noticed."""
    from chatinho.hooks import ALL_HOOKS
    root = pathlib.Path(__file__).resolve().parent.parent
    description = tomllib.loads((root / "pyproject.toml").read_text())["project"]["description"]
    said = [word for word in description.replace(",", " ").split() if word in _COUNTS]
    assert said[-1:] and description.split(said[-1])[1].lstrip().startswith("hooks"), description
    assert _COUNTS.index(said[-1]) == len(ALL_HOOKS)


def test_the_basic_agent_needs_no_deepagents():
    """What the agent connectors share, and the basic one, import with deep agents blocked."""
    script = """
import builtins, sys
real = builtins.__import__
def blocked(name, *a, **k):
    if name.split(".")[0] == "deepagents":
        raise ImportError("No module named %r" % name)
    return real(name, *a, **k)
builtins.__import__ = blocked
from chatinho.shared_kits.agent import AgentFactory, AgentPeer, BasicAgent, Interrupted
from chatinho.connectors.agents import BasicAgentConnector
try:
    from chatinho.shared_kits.agent import DeepAgent
except ImportError:
    print("deep-blocked")
print("deepagents" in sys.modules)
"""
    done = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, cwd=str(ROOT))
    assert done.returncode == 0, done.stderr
    assert done.stdout.split() == ["deep-blocked", "False"]


def test_using_a_workspace_does_not_import_deepagents(repo):
    """The adapter is behind its extra: a workspace in a plain session must not pull it in."""
    script = """
import asyncio, sys
from chatinho import ChatSession, GitWorktrees
async def main():
    session = ChatSession(workspaces=GitWorktrees(sys.argv[1]))
    await session.start()
    ws = await session.workspaces.provision("dev", "dev")
    await ws.write("a.txt", "a")
    await session.close()
asyncio.run(main())
print("deepagents" in sys.modules)
"""
    done = subprocess.run([sys.executable, "-c", script, str(repo)], capture_output=True, text=True,
                          cwd=str(ROOT))
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "False"
