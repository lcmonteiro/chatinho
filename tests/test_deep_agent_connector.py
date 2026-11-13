"""
DeepAgentConnector: a LangChain deep agent as a peer, working in its own workspace.

The model is scripted (``fakes.agent``); everything else is real — deep agents'
own ``create_deep_agent``, its file tools and middleware, and git worktrees in
the ``repo`` fixture — because what is promised is what those do together.
"""

import itertools
from typing import Any, Dict, List

import pytest

pytest.importorskip("deepagents")

from langchain_core.messages import AIMessage, BaseMessage, SystemMessage, ToolMessage  # noqa: E402

from chatinho import ChatMessage, HookAnswer, Query, Reply, ReplyStatus, require  # noqa: E402
from chatinho.connectors.agents.deep import DeepAgentConnector                  # noqa: E402
from chatinho.helpers.agent.deep import WHERE                                    # noqa: E402
from chatinho.workspaces import GitWorktrees, WorkspaceView, operation           # noqa: E402

from conftest import driven                                                      # noqa: E402
from fakes.agent import fake, says, this_run                                     # noqa: E402

_ids = itertools.count(1)


def steps(*calls: Dict[str, Any], answer: str = "done") -> Any:
    """Calls each tool in turn, one per model call, then answers with every result joined by '|'."""
    def script(messages: List[BaseMessage]) -> AIMessage:
        done = [m for m in this_run(messages) if isinstance(m, ToolMessage)]
        if len(done) < len(calls):
            name, args = next(iter(calls[len(done)].items()))
            call = {"name": name, "args": args, "id": "call-%d" % next(_ids)}
            return AIMessage(content="", tool_calls=[call])
        return AIMessage(content="|".join([answer] + [str(m.content) for m in done]))
    return script


def system_of(model) -> str:
    first = model.sent[-1][0]
    assert isinstance(first, SystemMessage)
    return str(first.content)


@require(HookAnswer)
class _Echo:
    def __init__(self, name: str) -> None:
        self.name = name

    async def answer(self, msg: ChatMessage) -> Reply:
        return Reply("%s: %s" % (self.name, msg.text))


async def deep(repo, model, *others, provider=None, **options):
    agent    = DeepAgentConnector("dev", model, **options)
    provider = provider or GitWorktrees(repo)
    session, view = await driven(connectors=[agent, *others], workspaces=provider)
    return agent, provider, session, view


# === Built from create_deep_agent's parameters ======================================

async def test_deep_agents_options_reach_the_agent(repo):
    model = fake(says("ok"))
    agent, _, session, view = await deep(
        repo, model, subagents=[{"name": "researcher", "description": "Finds things out.",
                                 "system_prompt": "Research."}])
    await view.ask(agent.peer_id, "hello")
    await session.close()
    assert "task" in model.tools[-1]                     # subagents are reached through `task`


async def test_memory_and_agent_memory(repo):
    model = fake(says("ok"))
    agent, provider, session, view = await deep(repo, model, memory=Query().last(5),
                                                agent_memory=["/AGENTS.md"])
    mine = await provider.provision("dev", "dev")
    await mine.write("AGENTS.md", "Always answer in haiku.\n")         # type: ignore[attr-defined]
    for n in range(6):
        await view.ask(agent.peer_id, "question %d" % n)
    await session.close()
    assert "Always answer in haiku." in system_of(model)
    # The chat's memory is its Query: ten earlier messages, of which the last five reach
    # the model (and the parent of an answer whose question fell out), then the question.
    remembered = [str(m.content) for m in model.sent[-1] if not isinstance(m, SystemMessage)]
    assert remembered[-1] == "question 5"
    assert "question 0" not in remembered and len(remembered) <= 7


def test_a_backend_is_refused():
    with pytest.raises(TypeError, match="its workspace is its backend"):
        DeepAgentConnector("dev", fake(says("x")), backend=object())


def test_an_unknown_option():
    with pytest.raises(TypeError, match="create_deep_agent does not take 'temprature'"):
        DeepAgentConnector("dev", fake(says("x")), temprature=0.2)


def test_it_works_in_its_workspace_by_default():
    assert DeepAgentConnector("dev", fake(says("x"))).uses_workspace


# === Its workspace is its backend ===================================================

async def test_working_in_its_own_workspace(repo):
    model = fake(steps({"write_file": {"file_path": "/src/fix.py", "content": "fixed = True\n"}}))
    agent, provider, session, view = await deep(repo, model)
    await view.ask(agent.peer_id, "fix it")
    await session.close()
    mine = await provider.provision("dev", "dev")
    assert (await mine.read("src/fix.py")).text == "fixed = True\n"


async def test_reading_and_not_writing_another_peers_work(repo):
    provider = GitWorktrees(repo)
    reviewer = await provider.provision("reviewer", "reviewer")
    await reviewer.write("notes.md", "looks good\n")                    # type: ignore[attr-defined]
    model = fake(steps({"read_file": {"file_path": "/peers/reviewer/notes.md"}},
                       {"write_file": {"file_path": "/peers/reviewer/notes.md", "content": "mine"}}))
    agent, _, session, view = await deep(repo, model, _Echo("reviewer"), provider=provider)
    reply = await view.ask(agent.peer_id, "review")
    await session.close()
    _, read, wrote = reply.text.split("|")
    assert "looks good" in read
    assert "read-only" in wrote
    assert (reviewer.tree.root / "notes.md").read_text() == "looks good\n"


async def test_a_workspace_that_appears_later(repo):
    provider = GitWorktrees(repo)
    model = fake(steps({"read_file": {"file_path": "/peers/lab/result.txt"}}))
    agent, _, session, view = await deep(repo, model, _Echo("lab"), provider=provider)
    first = await view.ask(agent.peer_id, "who has work?")
    lab = await provider.provision("lab", "lab")
    await lab.write("result.txt", "42\n")                              # type: ignore[attr-defined]
    second = await view.ask(agent.peer_id, "and now?")
    await session.close()
    assert "42" not in first.text
    assert "42" in second.text


async def test_asking_who_has_a_workspace_makes_none(repo):
    provider = GitWorktrees(repo)
    agent, _, session, view = await deep(repo, fake(says("ok")), _Echo("lab"), provider=provider)
    await view.ask(agent.peer_id, "hello")
    await session.close()
    assert await provider.names() == ["dev"]


async def test_a_chat_without_workspaces(caplog):
    model = fake(steps({"write_file": {"file_path": "/a.txt", "content": "kept in state"}}))
    agent = DeepAgentConnector("dev", model)
    session, view = await driven(connectors=[agent])
    reply = await view.ask(agent.peer_id, "write")
    await session.close()
    assert reply.status == ReplyStatus.ANSWERED
    assert not [t for t in model.tools[-1] if t.startswith("ws_")]
    assert "no workspace provider" in caplog.text
    assert WHERE not in system_of(model)


# === Only the ws_ tools its backend does not cover ==================================

async def test_the_default_ws_tools(repo):
    model = fake(says("ok"))
    agent, _, session, view = await deep(repo, model)
    await view.ask(agent.peer_id, "hello")
    await session.close()
    assert [t for t in model.tools[-1] if t.startswith("ws_")] == \
        ["ws_diff", "ws_log", "ws_commit", "ws_diff_of", "ws_log_of"]
    for own in ("read_file", "write_file", "edit_file", "ls", "glob", "grep"):
        assert own in model.tools[-1]


async def test_a_project_operation(repo):
    class MyView(WorkspaceView):
        @operation("List the symbols in a file")
        async def symbols(self, path: str) -> List[str]:
            return ["C"]

    from chatinho.workspaces import Workspace

    class MyWorkspace(Workspace, MyView):
        pass

    model = fake(says("ok"))
    agent, _, session, view = await deep(repo, model,
                                         provider=GitWorktrees(repo, view=MyView, workspace=MyWorkspace))
    await view.ask(agent.peer_id, "hello")
    await session.close()
    assert "ws_symbols" in model.tools[-1] and "ws_symbols_of" in model.tools[-1]


async def test_committing_through_ws_commit(repo):
    model = fake(steps({"write_file": {"file_path": "/a.txt", "content": "a\n"}},
                       {"ws_commit": {"message": "add a"}}))
    agent, provider, session, view = await deep(repo, model)
    await view.ask(agent.peer_id, "add a and commit")
    await session.close()
    assert (await (await provider.provision("dev", "dev")).log())[0].endswith(" add a")


# === It is told where things are ====================================================

async def test_the_users_prompt_is_kept(repo):
    model = fake(says("ok"))
    agent, _, session, view = await deep(repo, model, system_prompt="Be brief.")
    await view.ask(agent.peer_id, "hello")
    await session.close()
    system = system_of(model)
    assert WHERE in system and "Be brief." in system
    assert system.index(WHERE) < system.index("Be brief.")


# === Interrupted runs ===============================================================

async def test_an_interrupted_question(repo):
    model = fake(steps({"write_file": {"file_path": "/a.txt", "content": "x"}}))
    agent, _, session, view = await deep(repo, model, interrupt_on={"write_file": True})
    reply = await view.ask(agent.peer_id, "write it")
    await session.close()
    assert reply.status == ReplyStatus.ERROR
    assert "interrupted" in reply.text


async def test_an_interrupted_say(repo):
    model = fake(steps({"write_file": {"file_path": "/a.txt", "content": "x"}}))
    agent, _, session, view = await deep(repo, model, _Echo("other"), interrupt_on={"write_file": True})
    said = await view.say("write it")              # two answering peers: nobody is routed it
    await session.close()
    response = [m for m in view.context() if m.frm == agent.peer_id and m.reply_to == said]
    assert len(response) == 1 and "interrupted" in response[0].text


# === The same peer as BasicAgentConnector in the chat ====================================

async def test_asking_another_peer(repo):
    model = fake(steps({"ask_coder": {"question": "Write a test"}}))
    agent, _, session, view = await deep(repo, model, _Echo("coder"))
    reply = await view.ask(agent.peer_id, "get a test written")
    await session.close()
    assert reply.text == "done|coder: Write a test"


async def test_the_users_say(repo):
    agent, _, session, view = await deep(repo, fake(says("On it.")))
    said = await view.say("Fix the login bug")
    await session.close()
    assert [(m.text, m.reply_to) for m in view.context() if m.frm == agent.peer_id] == [("On it.", said)]
