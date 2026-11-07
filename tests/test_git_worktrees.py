"""
GitWorktrees: one worktree per peer, on a branch of its own, kept across restarts.

Run against real repositories, because what is being promised is git's state:
which branch exists, what ``git status`` shows, what the base holds.
"""

import subprocess
from typing import List

import pytest

from chatinho.workspaces import GitWorktrees, MergeConflict, Workspace, WorkspaceView, operation


def git(where, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=where, check=True, capture_output=True, text=True).stdout


# === Construction: the classes ======================================================

class MyView(WorkspaceView):
    @operation("List the symbols in a file")
    async def symbols(self, path: str) -> List[str]:
        return ["C"]


def test_a_workspace_class_that_does_not_extend_the_view(repo):
    with pytest.raises(TypeError, match="must subclass the view class MyView"):
        GitWorktrees(repo, view=MyView, workspace=Workspace)


def test_a_view_with_a_writing_operation(repo):
    class Leaky(WorkspaceView):
        @operation("Write anyway", writes=True)
        async def scribble(self, path: str) -> None:
            pass

    with pytest.raises(TypeError, match="scribble"):
        GitWorktrees(repo, view=Leaky, workspace=type("W", (Workspace, Leaky), {}))


async def test_an_extended_pair_gives_both_sides_the_added_read(repo):
    class MyWorkspace(Workspace, MyView):
        pass

    provider = GitWorktrees(repo, view=MyView, workspace=MyWorkspace)
    mine     = await provider.provision("dev", "dev")
    theirs   = await provider.provision("reviewer", "dev")
    assert isinstance(mine, MyWorkspace) and type(theirs) is MyView
    assert await theirs.symbols("x.py") == ["C"]                 # type: ignore[attr-defined]


# === Starting: the repository and the base ==========================================

async def test_not_a_repository(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    with pytest.raises(ValueError, match="not a git repository"):
        await GitWorktrees(plain).initialize()


async def test_a_base_that_does_not_exist(repo):
    with pytest.raises(ValueError, match="'nope' does not exist"):
        await GitWorktrees(repo, base="nope").initialize()


async def test_the_default_base_is_what_is_checked_out(repo):
    provider = GitWorktrees(repo)
    await provider.initialize()
    assert provider.base == "main"
    ws = await provider.provision("dev", "dev")
    assert (await ws.tree.git("merge-base", "HEAD", "main")).strip() == git(repo, "rev-parse", "main").strip()


async def test_a_base_given_by_name(repo):
    git(repo, "branch", "release")
    git(repo, "checkout", "--quiet", "-b", "elsewhere")
    provider = GitWorktrees(repo, base="release")
    ws       = await provider.provision("dev", "dev")
    assert ws.tree.base == "release"


# === Provisioning ===================================================================

async def test_created_on_first_use(repo):
    ws = await GitWorktrees(repo).provision("dev", "dev")
    assert isinstance(ws, Workspace)
    assert ws.tree.root == (repo / ".chatinho" / "worktrees" / "dev").resolve()
    assert git(ws.tree.root, "branch", "--show-current").strip() == "peer/dev"


async def test_someone_elses_is_a_view_without_writing_operations(repo):
    provider = GitWorktrees(repo)
    await provider.provision("dev", "dev")
    view = await provider.provision("reviewer", "dev")
    assert type(view) is WorkspaceView
    for name in ("write", "edit", "delete", "commit"):
        assert not hasattr(view, name)


async def test_a_command_gets_a_view(repo):
    view = await GitWorktrees(repo).provision(None, "dev")
    assert type(view) is WorkspaceView


async def test_one_tree_per_workspace(repo):
    provider = GitWorktrees(repo)
    mine     = await provider.provision("dev", "dev")
    theirs   = await provider.provision("reviewer", "dev")
    assert mine.tree is theirs.tree                 # so one lock


async def test_reused_after_a_restart(repo):
    ws = await GitWorktrees(repo).provision("dev", "dev")
    await ws.write("a.txt", "a")                    # type: ignore[attr-defined]
    await ws.commit("add a")                        # type: ignore[attr-defined]
    again = await GitWorktrees(repo).provision("dev", "dev")
    assert (await again.log())[0].endswith(" add a")


async def test_reused_when_only_the_branch_survived(repo):
    ws = await GitWorktrees(repo).provision("dev", "dev")
    await ws.write("a.txt", "a")                    # type: ignore[attr-defined]
    await ws.commit("add a")                        # type: ignore[attr-defined]
    git(repo, "worktree", "remove", "--force", str(ws.tree.root))
    again = await GitWorktrees(repo).provision("dev", "dev")
    assert (await again.log())[0].endswith(" add a")


async def test_close_keeps_the_work(repo):
    from chatinho.session import ChatSession
    provider = GitWorktrees(repo)
    session  = ChatSession(workspaces=provider)
    await session.start()
    ws = await provider.provision("dev", "dev")
    await ws.write("a.txt", "uncommitted")          # type: ignore[attr-defined]
    await session.close()
    assert (ws.tree.root / "a.txt").read_text() == "uncommitted"


async def test_the_repository_stays_clean(repo):
    before = git(repo, "status", "--porcelain")
    ws = await GitWorktrees(repo).provision("dev", "dev")
    await ws.write("a.txt", "a")                    # type: ignore[attr-defined]
    assert git(repo, "status", "--porcelain") == before == ""
    assert git(repo, "diff", "--name-only", "HEAD") == ""


async def test_viewing_without_creating(repo):
    with pytest.raises(KeyError):
        await GitWorktrees(repo).provision("reviewer", "ghost", create=False)


async def test_a_name_that_cannot_be_a_branch(repo):
    with pytest.raises(ValueError, match="cannot name a workspace"):
        await GitWorktrees(repo).provision("../x", "../x")


async def test_two_first_asks_create_it_once(repo):
    import asyncio
    provider = GitWorktrees(repo)
    first, second = await asyncio.gather(provider.provision("dev", "dev"),
                                         provider.provision("reviewer", "dev"))
    assert first.tree is second.tree


# === Listing, merging and dropping ==================================================

async def test_names_and_how_far_ahead(repo):
    provider = GitWorktrees(repo)
    ws = await provider.provision("dev", "dev")
    await provider.provision("lab", "lab")
    for n in range(2):
        await ws.write("a.txt", str(n))             # type: ignore[attr-defined]
        await ws.commit("c%d" % n)                  # type: ignore[attr-defined]
    assert await provider.names() == ["dev", "lab"]
    assert await provider.ahead("dev") == 2 and await provider.ahead("lab") == 0


async def test_merging_into_the_checked_out_base(repo):
    provider = GitWorktrees(repo)
    ws = await provider.provision("dev", "dev")
    await ws.write("a.txt", "a")                    # type: ignore[attr-defined]
    await ws.commit("add a")                        # type: ignore[attr-defined]
    await provider.merge("dev")
    assert "add a" in git(repo, "log", "--format=%s", "main")
    assert (repo / "a.txt").read_text() == "a"
    assert await provider.names() == ["dev"]


async def test_merging_into_a_base_checked_out_nowhere(repo):
    git(repo, "branch", "release")
    provider = GitWorktrees(repo, base="release")
    ws = await provider.provision("dev", "dev")
    await ws.write("a.txt", "a")                    # type: ignore[attr-defined]
    await ws.commit("add a")                        # type: ignore[attr-defined]
    await provider.merge("dev")
    assert "add a" in git(repo, "log", "--format=%s", "release")
    assert "add a" not in git(repo, "log", "--format=%s", "main")
    assert len(git(repo, "worktree", "list").splitlines()) == 2      # the temporary one is gone


async def test_a_conflicting_merge_is_aborted(repo):
    provider = GitWorktrees(repo)
    ws = await provider.provision("dev", "dev")
    await ws.write("README.md", "dev's\n")          # type: ignore[attr-defined]
    await ws.commit("dev's readme")                 # type: ignore[attr-defined]
    (repo / "README.md").write_text("main's\n")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "--quiet", "-am", "main's readme")
    before = git(repo, "rev-parse", "main")
    with pytest.raises(MergeConflict, match="README.md") as raised:
        await provider.merge("dev")
    assert raised.value.paths == ["README.md"]
    assert git(repo, "rev-parse", "main") == before
    assert git(repo, "status", "--porcelain") == ""


async def test_dropping(repo):
    provider = GitWorktrees(repo)
    ws = await provider.provision("dev", "dev")
    await ws.write("a.txt", "a")                    # type: ignore[attr-defined]
    await ws.commit("add a")                        # type: ignore[attr-defined]
    await provider.drop("dev")
    assert await provider.names() == []
    assert not ws.tree.root.exists()
    assert git(repo, "branch", "--list", "peer/dev") == ""
    fresh = await provider.provision("dev", "dev")
    assert await fresh.log() == []


async def test_merging_or_dropping_what_does_not_exist(repo):
    provider = GitWorktrees(repo)
    with pytest.raises(KeyError):
        await provider.merge("ghost")
    with pytest.raises(KeyError):
        await provider.drop("ghost")
