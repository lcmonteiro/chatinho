"""
WorkspaceBackend: a workspace as a LangChain deep agents backend.

Run against deep agents' real classes — the ABC, the result types,
``CompositeBackend`` and ``create_deep_agent`` — never a copy of them, so a
change in the protocol fails here rather than in somebody's agent.
"""

import asyncio
import itertools
from typing import Any, Dict, List

import pytest

pytest.importorskip("deepagents")

from deepagents import create_deep_agent                                         # noqa: E402
from deepagents.backends import CompositeBackend                                 # noqa: E402
from deepagents.backends.protocol import BackendProtocol, SandboxBackendProtocol  # noqa: E402
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage          # noqa: E402

from chatinho.workspaces import GitWorktrees, Workspace, operation               # noqa: E402
from chatinho.workspaces.deepagents import WorkspaceBackend                      # noqa: E402

from fakes.agent import fake                                                     # noqa: E402


async def backends(repo):
    """dev's backend, writable, and reviewer's, read through by dev."""
    provider = GitWorktrees(repo)
    mine     = await provider.provision("dev", "dev")
    reviewer = await provider.provision("reviewer", "reviewer")
    await reviewer.write("notes.md", "looks good\n")                        # type: ignore[attr-defined]
    return WorkspaceBackend(mine), WorkspaceBackend(await provider.provision("dev", "reviewer"))


# === What it is =====================================================================

async def test_it_is_a_backend_and_not_a_sandbox(repo):
    mine, _ = await backends(repo)
    assert isinstance(mine, BackendProtocol)
    assert not isinstance(mine, SandboxBackendProtocol)


# === Paths ==========================================================================

async def test_a_rooted_path(repo):
    mine, _ = await backends(repo)
    await mine.awrite("/src/app.py", "x = 1\n")
    assert (mine.workspace.tree.root / "src" / "app.py").read_text() == "x = 1\n"
    got = await mine.aread("/src/app.py")
    assert got.error is None and got.file_data is not None
    assert got.file_data["content"] == "x = 1\n"


async def test_escaping(repo):
    mine, _ = await backends(repo)
    got = await mine.aread("/../../etc/passwd")
    assert got.error is not None and "outside" in got.error and got.file_data is None


async def test_paths_come_back_absolute(repo):
    mine, _ = await backends(repo)
    await mine.awrite("/src/app.py", "")
    listed = await mine.als("/")
    assert {e["path"]: e.get("is_dir") for e in listed.entries or []} == {
        "/.gitignore": False, "/README.md": False, "/src/": True}
    assert [e["path"] for e in (await mine.als("/src")).entries or []] == ["/src/app.py"]
    assert [m["path"] for m in (await mine.aglob("*.py")).matches or []] == ["/src/app.py"]


# === Results, never exceptions =====================================================

async def test_a_missing_file(repo):
    mine, _ = await backends(repo)
    got = await mine.aread("/nope.txt")
    assert got.error is not None and "nope.txt" in got.error


async def test_an_ambiguous_edit(repo):
    mine, _ = await backends(repo)
    await mine.awrite("/a.txt", "x\nx\n")
    got = await mine.aedit("/a.txt", "x", "y")
    assert got.error is not None and "not unique" in got.error
    assert (await mine.aread("/a.txt")).file_data == {"content": "x\nx\n", "encoding": "utf-8"}
    done = await mine.aedit("/a.txt", "x", "y", replace_all=True)
    assert (done.path, done.occurrences, done.error) == ("/a.txt", 2, None)


async def test_a_glob_with_dot_dot(repo):
    mine, _ = await backends(repo)
    assert (await mine.aglob("../*")).error is not None


# === Each method through its operation ==============================================

async def test_read_reports_its_window(repo):
    mine, _ = await backends(repo)
    await mine.awrite("/ten.txt", "".join("%d\n" % n for n in range(1, 11)))
    got = await mine.aread("/ten.txt", offset=4, limit=3)
    assert (got.start_line, got.end_line, got.next_offset) == (5, 7, 7)
    assert got.file_data is not None and got.file_data["content"] == "5\n6\n7\n"
    last = await mine.aread("/ten.txt", offset=8, limit=5)
    assert (last.start_line, last.end_line, last.next_offset) == (9, 10, None)
    assert (await mine.aread("/ten.txt", offset=50)).error is not None
    assert (await mine.aread("/ten.txt", limit=0)).no_lines_requested


async def test_literal_grep(repo):
    mine, _ = await backends(repo)
    await mine.awrite("/a.py", "a.b(1)\naxb(2)\n")
    found = await mine.agrep("a.b(")
    assert found.matches == [{"path": "/a.py", "line": 1, "text": "a.b(1)"}]


async def test_max_count(repo):
    mine, _ = await backends(repo)
    await mine.awrite("/many.txt", "hit\n" * 30)
    found = await mine.agrep("hit", max_count=10)
    assert len(found.matches or []) == 10 and found.truncated
    assert len((await mine.agrep("hit")).matches or []) == 30


async def test_a_write_goes_through_the_lock(repo):
    order : List[str] = []

    class Watched(Workspace):
        @operation("Write, slowly", writes=True)
        async def write(self, path: str, text: str) -> None:
            order.append("start " + text)
            await asyncio.sleep(0.05)
            await self.tree.write_bytes(path, text.encode())
            order.append("end " + text)

    owner   = await GitWorktrees(repo, workspace=Watched).provision("dev", "dev")
    backend = WorkspaceBackend(owner)
    await asyncio.gather(owner.write("a.txt", "owner"), backend.awrite("/a.txt", "agent"))
    assert order == ["start owner", "end owner", "start agent", "end agent"]


async def test_uploads_and_downloads(repo):
    mine, _ = await backends(repo)
    up = await mine.aupload_files([("/blob.bin", b"\x00\xff"), ("/../x", b"no")])
    assert [(r.path, r.error) for r in up] == [("/blob.bin", None), ("/../x", "invalid_path")]
    down = await mine.adownload_files(["/blob.bin", "/missing"])
    assert [(r.content, r.error) for r in down] == [(b"\x00\xff", None), (None, "file_not_found")]


# === A view refuses writes ==========================================================

async def test_writing_to_someone_elses_workspace(repo):
    _, theirs = await backends(repo)
    root = theirs.workspace.tree.root
    for result in (await theirs.awrite("/notes.md", "mine now"),
                   await theirs.aedit("/notes.md", "good", "bad"),
                   await theirs.adelete("/notes.md")):
        assert result.error is not None and "reviewer's workspace" in result.error
    assert [r.error for r in await theirs.aupload_files([("/x", b"")])] == ["permission_denied"]
    assert (root / "notes.md").read_text() == "looks good\n"
    got = await theirs.aread("/notes.md")
    assert got.file_data is not None and got.file_data["content"] == "looks good\n"


# === Async only =====================================================================

async def test_called_synchronously(repo):
    mine, _ = await backends(repo)
    with pytest.raises(NotImplementedError, match="async only"):
        mine.read("/README.md")


# === In a real deep agent ===========================================================

_ids = itertools.count(1)


def steps(*calls: Dict[str, Any], answer: str = "done") -> Any:
    """A script calling each tool in turn, one per model call, then answering."""
    def script(messages: List[Any]) -> AIMessage:
        last = max(i for i, m in enumerate(messages) if isinstance(m, HumanMessage))
        done = [m for m in messages[last:] if isinstance(m, ToolMessage)]
        if len(done) < len(calls):
            call = dict(calls[len(done)], id="call-%d" % next(_ids))
            return AIMessage(content="", tool_calls=[call])
        return AIMessage(content=answer + "|" + "|".join(str(m.content) for m in done))
    return script


async def test_a_deep_agent_works_in_the_workspace(repo):
    mine, _ = await backends(repo)
    agent = create_deep_agent(model=fake(steps(
        {"name": "write_file", "args": {"file_path": "/fix.py", "content": "fixed = True\n"}},
        {"name": "read_file", "args": {"file_path": "/fix.py"}},
    )), backend=mine)
    out = await agent.ainvoke({"messages": [HumanMessage(content="fix it")]})
    assert (mine.workspace.tree.root / "fix.py").read_text() == "fixed = True\n"
    assert "fixed = True" in out["messages"][-1].content


async def test_a_composite_reads_a_peer_and_cannot_write_it(repo):
    mine, theirs = await backends(repo)
    composite = CompositeBackend(default=mine, routes={"/peers/reviewer/": theirs})
    agent = create_deep_agent(model=fake(steps(
        {"name": "read_file", "args": {"file_path": "/peers/reviewer/notes.md"}},
        {"name": "write_file", "args": {"file_path": "/peers/reviewer/notes.md", "content": "x"}},
        {"name": "execute", "args": {"command": "ls"}},
    )), backend=composite)
    out = await agent.ainvoke({"messages": [HumanMessage(content="review")]})
    read, wrote, ran = out["messages"][-1].content.split("|")[1:]
    assert "looks good" in read
    assert "read-only" in wrote
    assert (theirs.workspace.tree.root / "notes.md").read_text() == "looks good\n"
    assert "execut" in ran.lower() and "not" in ran.lower()
