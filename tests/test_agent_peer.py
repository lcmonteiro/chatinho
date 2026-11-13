"""
AgentPeer: the chat around any agent, made by a factory it is given.

The model is scripted (``fakes.agent``); the factory here is a small one of the
test's own, which is the point: anything with the four members of
``AgentFactory`` puts an agent in the chat, with no subclass.
"""

from typing import Any, Dict, FrozenSet, List

import pytest

from langchain.agents import create_agent

from chatinho import ChatMessage, HookAnswer, Reply, require
from chatinho.helpers.agent import AgentPeer
from chatinho.workspaces import GitWorktrees

from conftest import driven
from fakes.agent import fake, says


class Counting:
    """A factory of the test's own: ``create_agent``, and a record of every build."""

    name    : str            = "counting_factory"
    options : FrozenSet[str] = frozenset({"name", "system_prompt"})

    def __init__(self, covered: FrozenSet[str] = frozenset()) -> None:
        self.covered = covered
        self.builds  : List[List[str]] = []

    async def build(self, model: Any, tools: List[Any], options: Dict[str, Any], peer: Any) -> Any:
        self.builds.append([getattr(t, "name", None) for t in tools])
        return create_agent(model, tools=tools, **options)


@require(HookAnswer)
class _Echo:
    def __init__(self, name: str) -> None:
        self.name = name

    async def answer(self, msg: ChatMessage) -> Reply:
        return Reply("%s: %s" % (self.name, msg.text))


async def test_a_custom_factory():
    factory = Counting()
    peer    = AgentPeer("helper", fake(says("It is sunny.")), factory)
    session, view = await driven(connectors=[peer, _Echo("coder")])
    reply = await view.ask(peer.peer_id, "weather?")
    await session.close()
    assert reply.text == "It is sunny."
    assert len(factory.builds) == 1 and "ask_coder" in factory.builds[0]


def test_not_built_when_created():
    factory = Counting()
    AgentPeer("helper", fake(says("x")), factory)
    assert factory.builds == []


async def test_rebuilt_for_a_new_peer():
    factory = Counting()
    peer    = AgentPeer("helper", fake(says("ok")), factory)
    session, view = await driven(connectors=[peer])
    await view.ask(peer.peer_id, "one")
    session.add_connector(_Echo("lab"))
    await view.ask(peer.peer_id, "two")
    await session.close()
    assert len(factory.builds) == 2
    assert "ask_lab" not in factory.builds[0] and "ask_lab" in factory.builds[1]


def test_an_option_the_factory_does_not_take():
    with pytest.raises(TypeError, match="counting_factory does not take 'temperature'"):
        AgentPeer("helper", fake(says("x")), Counting(), temperature=0.2)


async def test_covered_operations_get_no_tools(repo):
    model = fake(says("ok"))
    peer  = AgentPeer("helper", model, Counting(covered=frozenset({"read"})), workspace=True)
    session, view = await driven(connectors=[peer], workspaces=GitWorktrees(repo))
    await view.ask(peer.peer_id, "hello")
    await session.close()
    tools = model.tools[-1]
    assert "ws_read" not in tools and "ws_read_of" not in tools
    assert "ws_write" in tools and "ws_diff_of" in tools


def test_not_in_the_top_level_api():
    import chatinho
    with pytest.raises(AttributeError):
        chatinho.AgentPeer
