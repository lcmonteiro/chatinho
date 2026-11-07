"""
The workspace role in a session: who is granted what, and what the provider is not.

The provider is a role like the router — no id, in no roster, hearing nothing —
and the grant is the one door: a peer's own workspace back writable, anyone
else's back as a view.
"""

import asyncio
import time
from typing import Any, List, Optional

import pytest

from chatinho import (
    ChatMessage,
    HookAnswer,
    HookListen,
    HookProvision,
    HookWorkspace,
    NoWorkspaceProvider,
    Reply,
    connector,
    require,
)
from chatinho.hooks import HookExecute, WorkspaceGrant, tool
from chatinho.message import LOCAL
from chatinho.session import ChatSession
from chatinho.workspaces import GitWorktrees, Workspace, WorkspaceView

from conftest import driven


@connector("dev")
@require(HookWorkspace)
class Worker:
    """A peer that works in workspaces, and nothing else."""

    workspace : WorkspaceGrant


@tool("peek", "Reads a workspace")
@require(HookExecute)
@require(HookWorkspace)
class Peek:
    workspace : WorkspaceGrant

    async def execute(self, args: str = "", by: int = LOCAL, **kwargs: Any) -> Reply:
        view = await self.workspace(args or None)
        return Reply((await view.read("README.md")).text)


async def session_with(repo, *peers: Any, commands: Optional[List[Any]] = None) -> Any:
    session, _ = await driven(connectors=list(peers), commands=commands or [],
                              workspaces=GitWorktrees(repo))
    return session


# === The provider is a role =========================================================

async def test_the_provider_is_in_no_roster(repo):
    worker  = Worker()
    session = await session_with(repo, worker)
    assert sorted(w.name for w in session._peers().values()) == ["dev", "driver"]
    assert session.id_of("workspaces") is None
    await session.close()


async def test_the_provider_is_started_and_hears_nothing(repo):
    provider = GitWorktrees(repo)
    session, view = await driven(workspaces=provider)
    assert provider.base == "main"                  # initialize() ran at start()
    await view.say("hello")
    await session.close()
    assert not hasattr(provider, "listen")


async def test_two_providers(repo):
    session = ChatSession(workspaces=GitWorktrees(repo))
    with pytest.raises(ValueError, match="HookProvision"):
        session.add_connector(GitWorktrees(repo))


async def test_a_provider_is_not_a_command_either(repo):
    @tool("ws2")
    @require(HookExecute)
    @require(HookProvision)
    class Both(GitWorktrees):
        async def execute(self, args: str = "", **kwargs: Any) -> Reply:
            return Reply("")

    with pytest.raises(ValueError, match="not a peer"):
        ChatSession(commands=[Both(repo)])


def test_a_provider_that_declares_nothing():
    with pytest.raises(TypeError, match="HookProvision"):
        ChatSession(workspaces=object())


# === The grant ======================================================================

async def test_its_own_workspace(repo):
    worker  = Worker()
    session = await session_with(repo, worker)
    ws = await worker.workspace()
    assert isinstance(ws, Workspace) and ws.name == "dev"
    await ws.write("a.txt", "hi")
    assert (ws.tree.root / "a.txt").read_text() == "hi"
    await session.close()


async def test_its_own_name_is_its_own_workspace(repo):
    worker  = Worker()
    session = await session_with(repo, worker)
    assert isinstance(await worker.workspace("dev"), Workspace)
    await session.close()


async def test_another_peers_workspace_is_read_only(repo):
    dev, reviewer = Worker(), Worker()
    reviewer.name = "reviewer"
    session = await session_with(repo, dev, reviewer)
    mine = await dev.workspace()
    await mine.write("a.txt", "dev's work")
    theirs = await reviewer.workspace("dev")
    assert type(theirs) is WorkspaceView
    assert (await theirs.read("a.txt")).text == "dev's work"
    # The restriction is structural: there is nothing to call. mypy refuses
    # `theirs.write(...)` too, the view's class having no such attribute.
    for name in ("write", "edit", "delete", "commit"):
        assert not hasattr(theirs, name)
    await session.close()


async def test_a_peer_in_the_chat_has_a_workspace_before_it_asks(repo):
    dev, reviewer = Worker(), Worker()
    reviewer.name = "reviewer"
    session = await session_with(repo, dev, reviewer)
    view = await reviewer.workspace("dev")          # dev never asked for its own
    assert await view.ls() == [".gitignore", "README.md"]
    await session.close()


async def test_no_provider():
    worker = Worker()
    session, _ = await driven(connectors=[worker])
    with pytest.raises(NoWorkspaceProvider, match="no workspace provider"):
        await worker.workspace()
    await session.close()


async def test_an_unknown_name(repo):
    worker  = Worker()
    session = await session_with(repo, worker)
    with pytest.raises(KeyError, match="nobody"):
        await worker.workspace("nobody")
    await session.close()


async def test_a_workspace_that_outlived_its_peer_is_still_readable(repo):
    await GitWorktrees(repo).provision("gone", "gone")
    worker  = Worker()
    session = await session_with(repo, worker)
    assert type(await worker.workspace("gone")) is WorkspaceView
    await session.close()


async def test_a_command_reads_a_named_workspace(repo):
    worker  = Worker()
    session, view = await driven(connectors=[worker], commands=[Peek()], workspaces=GitWorktrees(repo))
    assert await view.command("peek", "dev") == "# repo\n"
    await session.close()


async def test_a_command_owns_no_workspace(repo):
    session, view = await driven(commands=[Peek()], workspaces=GitWorktrees(repo))
    with pytest.raises(ValueError, match="A command owns no workspace"):
        await view.command("peek")
    await session.close()


# === Nothing blocks =================================================================

@connector("echo")
@require(HookListen)
@require(HookAnswer)
class Stamp:
    """Notes when it heard a say."""

    def __init__(self) -> None:
        self.heard_at : Optional[float] = None

    async def listen(self, msg: ChatMessage) -> None:
        if msg.text == "ping":
            self.heard_at = time.monotonic()

    async def answer(self, msg: ChatMessage) -> Reply:
        return Reply("pong")


async def test_a_long_search_does_not_hold_up_the_chat(repo):
    worker, stamp = Worker(), Stamp()
    session, view = await driven(connectors=[worker, stamp], workspaces=GitWorktrees(repo))
    ws = await worker.workspace()
    for n in range(40):
        await ws.write("big/f%02d.txt" % n, ("line of text %d\n" % n) * 20000)

    async def search() -> float:
        await ws.grep(r"(a|b|c|d|e|f|g|h|i|j|k|l|m|n|o|p|q|r|s|t)+ of text 3\d")
        return time.monotonic()

    searching = asyncio.ensure_future(search())
    await asyncio.sleep(0.05)
    await view.say("ping")
    finished = await searching
    await session.close()
    assert stamp.heard_at is not None and stamp.heard_at < finished
