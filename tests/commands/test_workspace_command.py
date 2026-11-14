"""
``/ws``: listing, diffing, merging and dropping workspaces — the last two only for the user.
"""

import subprocess
from typing import Any

import pytest

from chatinho import HookInvoke, HookWorkspace, Invoke, WorkspaceGrant, connector, require
from chatinho.commands import WorkspaceCommand
from chatinho.message import TOOL
from chatinho.workspaces import GitWorktrees, MergeConflict

from conftest import driven


def git(where, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=where, check=True, capture_output=True, text=True).stdout


@connector("dev")
@require(HookWorkspace)
@require(HookInvoke)
class Dev:
    """A peer with a workspace, that can also run commands — as an agent's run_ws tool does."""

    workspace : WorkspaceGrant
    invoke    : Invoke


async def chat_with_ws(repo) -> Any:
    provider = GitWorktrees(repo)
    dev      = Dev()
    session, view = await driven(connectors=[dev], commands=[WorkspaceCommand(provider)],
                                 workspaces=provider)
    return session, view, dev


async def committed(dev: Dev, n: int = 2) -> None:
    ws = await dev.workspace()
    for i in range(n):
        await ws.write("a.txt", "version %d\n" % i)
        await ws.commit("change %d" % i)


async def test_listing(repo):
    session, view, dev = await chat_with_ws(repo)
    assert await view.command("ws") == "No workspaces yet."
    await committed(dev, 2)
    assert await view.command("ws") == "Workspaces:\n  dev  peer/dev  2 commits ahead of main"
    await session.close()


async def test_the_diff_is_an_attachment(repo):
    session, view, dev = await chat_with_ws(repo)
    await committed(dev, 1)
    assert await view.command("ws", "diff dev") == "dev's work: [dev.diff](dev.diff)"
    await session.close()
    answer = [m for m in view.context() if m.frm == TOOL][-1]
    assert answer.text == "dev's work: [dev.diff](dev.diff)"


async def test_the_diff_attachment_holds_the_diff(repo):
    provider = GitWorktrees(repo)
    ws = await provider.provision("dev", "dev")
    await ws.write("a.txt", "hello\n")                  # type: ignore[attr-defined]
    reply = await WorkspaceCommand(provider).execute("diff dev")
    (attached,) = reply.attachments
    assert attached.name == "dev.diff" and attached.media_type == "text/x-diff"
    assert b"+hello" in attached.data


async def test_merging(repo):
    session, view, dev = await chat_with_ws(repo)
    await committed(dev, 1)
    assert await view.command("ws", "merge dev") == "Merged dev's workspace into main."
    assert "change 0" in git(repo, "log", "--format=%s", "main")
    assert await view.command("ws") == "Workspaces:\n  dev  peer/dev  0 commits ahead of main"
    await session.close()


async def test_a_model_cannot_merge(repo):
    session, view, dev = await chat_with_ws(repo)
    await committed(dev, 1)
    before = git(repo, "rev-parse", "main")
    with pytest.raises(PermissionError, match="Only the user can merge"):
        await dev.invoke("ws", "merge dev")
    with pytest.raises(PermissionError, match="Only the user can drop"):
        await dev.invoke("ws", "drop dev")
    assert git(repo, "rev-parse", "main") == before
    assert await dev.invoke("ws", "diff dev") is not None      # but it can look
    await session.close()


async def test_a_conflicting_merge(repo):
    session, view, dev = await chat_with_ws(repo)
    ws = await dev.workspace()
    await ws.write("README.md", "dev's\n")
    await ws.commit("dev's readme")
    (repo / "README.md").write_text("main's\n")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "--quiet", "-am", "main's readme")
    before = git(repo, "rev-parse", "main")
    with pytest.raises(MergeConflict, match="README.md"):
        await view.command("ws", "merge dev")
    assert git(repo, "rev-parse", "main") == before
    await session.close()


async def test_dropping(repo):
    session, view, dev = await chat_with_ws(repo)
    await committed(dev, 1)
    assert await view.command("ws", "drop dev") == "Dropped dev's workspace."
    assert git(repo, "branch", "--list", "peer/dev") == ""
    assert await (await dev.workspace()).log() == []           # a fresh one, from the base
    await session.close()


@pytest.mark.parametrize("args, error", [
    ("frobnicate dev", ValueError),
    ("diff", ValueError),
    ("diff ghost", KeyError),
    ("merge ghost", KeyError),
])
async def test_what_it_refuses(repo, args, error):
    session, view, dev = await chat_with_ws(repo)
    with pytest.raises(error):
        await view.command("ws", args)
    await session.close()


async def test_the_builders_add_no_command_of_their_own(repo):
    """/ws is chosen like any command: given workspaces, a builder adds nothing to the list."""
    from chatinho import HelpCommand
    from chatinho.builder import build_chat_session

    session = build_chat_session(commands=[HelpCommand()], workspaces=GitWorktrees(repo))
    assert list(session.commands) == ["help"]


async def test_help_lists_ws_when_it_is_given(repo):
    from chatinho import HelpCommand
    from chatinho.builder import build_chat_session

    provider = GitWorktrees(repo)
    session  = build_chat_session(commands=[HelpCommand(), WorkspaceCommand(provider)], workspaces=provider)
    assert "/ws - " in (await session.commands["help"].execute()).text
