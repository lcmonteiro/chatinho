"""
What can be done in a workspace: the operations, their declarations, and the Tree under them.

Every test runs against a real repository (the ``repo`` fixture) because the
operations are thin over git and the file system, and a fake of either would
test the fake.
"""

import asyncio
import os
import time
from typing import List

import pytest

from chatinho.workspaces import (
    GitWorktrees,
    Lines,
    Workspace,
    WorkspaceView,
    operation,
    operations_of,
)


async def own(repo, name: str = "dev") -> Workspace:
    ws = await GitWorktrees(repo).provision(name, name)
    assert isinstance(ws, Workspace)
    return ws


# === Declaring operations ===========================================================

def test_the_default_view_operations_in_order():
    ops = operations_of(WorkspaceView)
    assert [op.name for op in ops] == ["ls", "read", "glob", "grep", "diff", "log"]
    assert not any(op.writes for op in ops)


def test_a_workspace_inherits_the_view_and_adds_writing_ones():
    ops = operations_of(Workspace)
    assert [op.name for op in ops] == ["ls", "read", "glob", "grep", "diff", "log",
                                       "write", "edit", "delete", "commit"]
    assert [op.name for op in ops if op.writes] == ["write", "edit", "delete", "commit"]


def test_an_operation_carries_its_description_and_parameters():
    grep = next(op for op in operations_of(WorkspaceView) if op.name == "grep")
    assert "regular expression" in grep.description
    assert [p.name for p in grep.parameters] == ["pattern", "path", "glob", "multiline", "limit"]


def test_operations_of_an_instance_is_of_its_class():
    assert operations_of(WorkspaceView) == operations_of(WorkspaceView.__new__(WorkspaceView))


def test_a_plain_def_is_refused_where_the_class_is_defined():
    with pytest.raises(TypeError, match="symbols"):
        class Broken(WorkspaceView):
            @operation("not a coroutine")
            def symbols(self, path: str) -> List[str]:
                return []


def test_an_added_operation_is_discovered():
    class MyView(WorkspaceView):
        @operation("List the symbols in a file")
        async def symbols(self, path: str) -> List[str]:
            return []

    assert [op.name for op in operations_of(MyView)][-1] == "symbols"


# === The Tree: the one door to a path ===============================================

async def test_dot_dot_is_refused(repo):
    ws = await own(repo)
    with pytest.raises(ValueError, match="outside"):
        await ws.read("../../etc/passwd")


async def test_an_absolute_path_is_refused(repo):
    ws = await own(repo)
    with pytest.raises(ValueError, match="absolute"):
        await ws.read("/etc/passwd")


async def test_a_link_out_of_the_workspace_is_refused(repo, tmp_path):
    ws = await own(repo)
    secret = tmp_path / "secret.txt"
    secret.write_text("no")
    os.symlink(secret, ws.tree.root / "link.txt")
    with pytest.raises(ValueError, match="outside"):
        await ws.read("link.txt")


async def test_git_metadata_is_not_reachable(repo):
    ws = await own(repo)
    with pytest.raises(ValueError, match="metadata"):
        await ws.write(".git", "broken")


# === Reading ========================================================================

async def test_ls_marks_directories_and_hides_git(repo):
    ws = await own(repo)
    await ws.write("src/app.py", "x = 1\n")
    assert await ws.ls() == [".gitignore", "README.md", "src/"]
    assert await ws.ls("src") == ["app.py"]


async def test_reading_a_window(repo):
    ws = await own(repo)
    await ws.write("ten.txt", "".join("line %d\n" % n for n in range(1, 11)))
    got = await ws.read("ten.txt", offset=4, limit=3)
    assert got == Lines("line 5\nline 6\nline 7\n", start=5, more=True)


async def test_a_window_past_the_end_says_nothing_remains(repo):
    ws = await own(repo)
    await ws.write("ten.txt", "".join("line %d\n" % n for n in range(1, 11)))
    got = await ws.read("ten.txt", offset=8, limit=5)
    assert (got.text, got.start, got.more) == ("line 9\nline 10\n", 9, False)


async def test_degenerate_windows_do_not_fail(repo):
    ws = await own(repo)
    await ws.write("ten.txt", "a\nb\n")
    assert (await ws.read("ten.txt", offset=-3, limit=1)).text == "a\n"
    assert (await ws.read("ten.txt", limit=0)).text == ""


async def test_reading_a_missing_file_names_it(repo):
    ws = await own(repo)
    with pytest.raises(FileNotFoundError, match="nope.txt"):
        await ws.read("nope.txt")


async def test_reading_uncommitted_work_through_a_view(repo):
    provider = GitWorktrees(repo)
    dev      = await provider.provision("dev", "dev")
    await dev.write("a.txt", "work in progress\n")      # type: ignore[attr-defined]
    view     = await provider.provision("reviewer", "dev")
    assert (await view.read("a.txt")).text == "work in progress\n"


async def test_glob_matches_a_name_at_any_depth(repo):
    ws = await own(repo)
    await ws.write("a.py", "")
    await ws.write("src/app/main.py", "")
    await ws.write("src/app/notes.md", "")
    assert await ws.glob("*.py") == ["a.py", "src/app/main.py"]
    assert await ws.glob("src/**/*.py") == ["src/app/main.py"]
    assert await ws.glob("*.py", path="src") == ["src/app/main.py"]


async def test_glob_leaves_ignored_files_out(repo):
    ws = await own(repo)
    await ws.write("kept.log.txt", "")
    await ws.write("debug.log", "")
    await ws.write("ignored/x.txt", "")
    assert await ws.glob("*") == [".gitignore", "README.md", "kept.log.txt"]


async def test_the_diff_shows_committed_and_uncommitted_work(repo):
    ws = await own(repo)
    await ws.write("a.txt", "committed\n")
    await ws.commit("add a")
    await ws.write("b.txt", "not yet\n")
    diff = await ws.diff()
    assert "a.txt" in diff and "+committed" in diff
    assert "b.txt" in diff and "+not yet" in diff


async def test_the_diff_leaves_the_owners_index_alone(repo):
    ws = await own(repo)
    await ws.write("b.txt", "not yet\n")
    await ws.diff()
    assert (await ws.tree.git("diff", "--cached", "--name-only")).strip() == ""


async def test_the_log_is_newest_first(repo):
    ws = await own(repo)
    await ws.write("a.txt", "1")
    first = await ws.commit("one")
    await ws.write("a.txt", "2")
    await ws.commit("two")
    log = await ws.log()
    assert [line.split(" ", 1)[1] for line in log] == ["two", "one"]
    assert first.startswith(log[1].split(" ")[0])


# === grep ===========================================================================

SOURCE = "class C:\n\n    def answer(self):\n        x = 1\n        return Reply(x)\n"


async def test_a_match_on_one_line(repo):
    ws = await own(repo)
    await ws.write("c.py", SOURCE)
    found = await ws.grep(r"def answer")
    assert [(m.path, m.start, m.end) for m in found.matches] == [("c.py", 3, 3)]
    assert found.matches[0].text == "    def answer(self):\n"


async def test_a_match_across_lines(repo):
    ws = await own(repo)
    await ws.write("c.py", SOURCE)
    found = await ws.grep(r"def answer\(.*?return", multiline=True)
    assert [(m.start, m.end) for m in found.matches] == [(3, 5)]
    assert "def answer" in found.matches[0].text and "return Reply" in found.matches[0].text


async def test_the_same_pattern_without_multiline(repo):
    ws = await own(repo)
    await ws.write("c.py", SOURCE)
    assert (await ws.grep(r"def answer\(.*?return")).matches == ()


async def test_ignored_files_are_not_searched(repo):
    ws = await own(repo)
    await ws.write("debug.log", "needle\n")
    await ws.write("kept.txt", "needle\n")
    assert [m.path for m in (await ws.grep("needle")).matches] == ["kept.txt"]


async def test_grep_filters_by_glob(repo):
    ws = await own(repo)
    await ws.write("a.py", "needle\n")
    await ws.write("a.txt", "needle\n")
    assert [m.path for m in (await ws.grep("needle", glob="*.py")).matches] == ["a.py"]


async def test_more_matches_than_the_limit(repo):
    ws = await own(repo)
    await ws.write("many.txt", "hit\n" * 150)
    found = await ws.grep("hit", limit=100)
    assert len(found.matches) == 100 and found.truncated


async def test_exactly_the_limit_is_not_truncated(repo):
    ws = await own(repo)
    await ws.write("many.txt", "hit\n" * 5)
    found = await ws.grep("hit", limit=5)
    assert len(found.matches) == 5 and not found.truncated


async def test_a_bad_pattern(repo):
    ws = await own(repo)
    with pytest.raises(ValueError, match="Invalid pattern"):
        await ws.grep("(unclosed")


async def test_a_long_match_is_cut_and_says_so(repo):
    ws = await own(repo)
    await ws.write("long.txt", "start" + "x" * 2000 + "\n")
    text = (await ws.grep("start.*", multiline=True)).matches[0].text
    assert len(text) < 600 and "cut" in text


async def test_binary_files_are_skipped(repo):
    ws = await own(repo)
    await ws.tree.write_bytes("blob.bin", b"needle\xff\xfe\n")
    await ws.write("text.txt", "needle\n")
    assert [m.path for m in (await ws.grep("needle")).matches] == ["text.txt"]


# === Writing ========================================================================

async def test_write_creates_folders(repo):
    ws = await own(repo)
    await ws.write("deep/er/a.txt", "hi")
    assert (ws.tree.root / "deep/er/a.txt").read_text() == "hi"


async def test_an_exact_edit(repo):
    ws = await own(repo)
    await ws.write("a.txt", "x = 1\n")
    assert await ws.edit("a.txt", "x = 1", "x = 2") == 1
    assert (await ws.read("a.txt")).text == "x = 2\n"


async def test_an_ambiguous_edit_changes_nothing(repo):
    ws = await own(repo)
    await ws.write("a.txt", "x = 1\nx = 1\n")
    with pytest.raises(ValueError, match="not unique"):
        await ws.edit("a.txt", "x = 1", "x = 2")
    assert (await ws.read("a.txt")).text == "x = 1\nx = 1\n"
    assert await ws.edit("a.txt", "x = 1", "x = 2", replace_all=True) == 2


async def test_an_edit_of_text_that_is_not_there(repo):
    ws = await own(repo)
    await ws.write("a.txt", "x = 1\n")
    with pytest.raises(ValueError, match="does not occur"):
        await ws.edit("a.txt", "y", "z")


async def test_delete_a_file_and_a_folder(repo):
    ws = await own(repo)
    await ws.write("a.txt", "")
    await ws.write("d/b.txt", "")
    await ws.delete("a.txt")
    await ws.delete("d")
    assert await ws.ls() == [".gitignore", "README.md"]
    with pytest.raises(FileNotFoundError):
        await ws.delete("a.txt")


async def test_write_commit_log(repo):
    ws = await own(repo)
    await ws.write("a.txt", "a")
    sha = await ws.commit("add a")
    newest = (await ws.log())[0]
    assert newest.endswith(" add a") and sha.startswith(newest.split(" ")[0])


async def test_the_commit_is_authored_by_the_peer(repo):
    ws = await own(repo)
    await ws.write("a.txt", "a")
    await ws.commit("add a")
    assert (await ws.tree.git("log", "-1", "--format=%an")).strip() == "dev"


async def test_nothing_to_commit(repo):
    ws = await own(repo)
    with pytest.raises(ValueError, match="Nothing to commit"):
        await ws.commit("x")
    assert await ws.log() == []


async def test_the_base_is_untouched(repo):
    ws = await own(repo)
    before = (await ws.tree.git("rev-parse", "main")).strip()
    await ws.write("a.txt", "a")
    await ws.commit("add a")
    assert (await ws.tree.git("rev-parse", "main")).strip() == before


# === The lock =======================================================================

class Slow(Workspace):
    """Writes that take a while, and reads that do too, to see who waits for whom."""

    events : List[str] = []

    @operation("A slow write", writes=True)
    async def slow_write(self, tag: str) -> None:
        self.events.append("start " + tag)
        await asyncio.sleep(0.1)
        self.events.append("end " + tag)

    @operation("A slow read")
    async def slow_read(self, tag: str) -> None:
        self.events.append("start " + tag)
        await asyncio.sleep(0.1)
        self.events.append("end " + tag)


async def test_writes_run_one_at_a_time_in_call_order(repo):
    ws = await GitWorktrees(repo, workspace=Slow).provision("dev", "dev")
    Slow.events = []
    await asyncio.gather(ws.slow_write("1"), ws.slow_write("2"))   # type: ignore[attr-defined]
    assert Slow.events == ["start 1", "end 1", "start 2", "end 2"]


async def test_reads_do_not_wait_for_each_other(repo):
    ws = await GitWorktrees(repo, workspace=Slow).provision("dev", "dev")
    Slow.events = []
    begun = time.monotonic()
    await asyncio.gather(ws.slow_read("1"), ws.slow_read("2"))     # type: ignore[attr-defined]
    assert Slow.events[:2] == ["start 1", "start 2"]
    assert time.monotonic() - begun < 0.18


async def test_two_writes_of_one_file_end_with_the_last_called(repo):
    ws = await own(repo)
    await asyncio.gather(ws.write("a.txt", "first"), ws.write("a.txt", "second"))
    assert (await ws.read("a.txt")).text == "second"
