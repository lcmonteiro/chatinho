"""
Tests for what the worktree provider logs: each merge and drop, and a merge that fails.
"""

import logging
import subprocess
from typing import List

import pytest

from chatinho.workspaces import GitWorktrees, MergeConflict


@pytest.fixture(autouse=True)
def everything(caplog):
    caplog.set_level(logging.DEBUG, logger="chatinho")
    return caplog


def git(where, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=where, check=True, capture_output=True, text=True).stdout


def having(caplog, *words: str, level: int = logging.DEBUG) -> List[str]:
    return [r.getMessage() for r in caplog.records
            if r.name.startswith("chatinho") and r.levelno >= level
            and all(w in r.getMessage() for w in words)]


# @ac AC-WS-006.1
async def test_a_merge_is_logged_with_its_branch_and_base(repo, caplog):
    provider = GitWorktrees(repo)
    ws = await provider.provision("dev", "dev")
    await ws.write("a.txt", "a")                    # type: ignore[attr-defined]
    await ws.commit("add a")                        # type: ignore[attr-defined]
    await provider.merge("dev")
    assert having(caplog, "merged", "dev", "peer/dev", "main", level=logging.INFO)


# @ac AC-WS-006.2
async def test_a_drop_is_logged_with_its_branch(repo, caplog):
    provider = GitWorktrees(repo)
    await provider.provision("dev", "dev")
    await provider.drop("dev")
    assert having(caplog, "dropped", "dev", "peer/dev", level=logging.INFO)


# @ac AC-WS-006.3
async def test_a_merge_that_fails_is_a_warning_and_still_fails(repo, caplog):
    provider = GitWorktrees(repo)
    ws = await provider.provision("dev", "dev")
    await ws.write("README.md", "dev's\n")          # type: ignore[attr-defined]
    await ws.commit("dev's readme")                 # type: ignore[attr-defined]
    (repo / "README.md").write_text("main's\n")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "--quiet", "-am", "main's readme")
    with pytest.raises(MergeConflict):
        await provider.merge("dev")
    warned = having(caplog, "dev", level=logging.WARNING)
    assert warned
    assert any("README.md" in line or "conflict" in line.lower() for line in warned)
    assert not having(caplog, "merged", level=logging.INFO)
