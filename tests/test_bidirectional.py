"""Tests for the inbound direction: the agent asks, the user answers.

A connector is a link between the user and an agent. The outbound half — the
user asks, the far side answers — is ``ask``. This covers the other half: the
far side starts the exchange through ``ask_user``, and the user's reply is
routed back through ``answer``, correlated by the far side's own id.
"""

import pytest

from chatinho import BaseConnector, BidirectionalConnector, ChatSession


class Agent(BidirectionalConnector):
    """A two-way link that records both directions."""

    def __init__(self, name: str = "agent") -> None:
        super().__init__(name)
        self.asked: list = []      # what we sent out
        self.answered: list = []   # what the user replied, with its correlation
        self.started = False
        self.stopped = False

    def initialize(self) -> None:
        self.started = True

    def shutdown(self) -> None:
        self.stopped = True

    def ask(self, message: str, **kwargs) -> str:
        self.asked.append(message)
        return "agent says: %s" % message

    def answer(self, correlation_id, text: str) -> None:
        self.answered.append((correlation_id, text))


class OutboundOnly(BaseConnector):
    """A one-way link: the user asks, nothing ever arrives unprompted."""

    def __init__(self, name: str = "one-way") -> None:
        super().__init__(name)

    def initialize(self) -> None:
        pass

    def ask(self, message: str, **kwargs) -> str:
        return "answer"


# === Direction is declared by type ==============================================


def test_a_one_way_connector_implements_only_the_outbound_half():
    """ISP: it is never asked for attach() or answer()."""
    connector = OutboundOnly()
    assert not isinstance(connector, BidirectionalConnector)
    assert not hasattr(connector, "answer")


def test_the_session_only_attaches_bidirectional_connectors():
    one_way, two_way = OutboundOnly(), Agent()
    ChatSession(connectors=[one_way, two_way])
    assert two_way._inbox is not None


# === The agent asks =============================================================


def test_ask_user_puts_the_question_in_the_history():
    agent = Agent()
    session = ChatSession(connectors=[agent])
    agent.ask_user("Deploy to production?", correlation_id="task-1")

    assert len(session.messages) == 1
    question = session.messages[0]
    assert question.text == "Deploy to production?"
    assert question.is_sent_by_me is False
    assert question.origin == "agent"
    assert question.correlation_id == "task-1"


def test_ask_user_before_registration_is_refused():
    with pytest.raises(RuntimeError, match="not attached"):
        Agent().ask_user("ninguem me ouve")


def test_deliver_rejects_an_unknown_connector():
    with pytest.raises(ValueError):
        ChatSession().deliver("nope", "ola")


# === The user answers ===========================================================


def test_replying_to_the_question_routes_the_answer_back():
    agent = Agent()
    session = ChatSession(connectors=[agent])
    question = agent.ask_user("Deploy to production?", correlation_id="task-1")

    session.send_message("yes, go ahead", reply_to=question)

    assert agent.answered == [("task-1", "yes, go ahead")]


def test_an_unrelated_message_is_not_routed_anywhere():
    agent = Agent()
    session = ChatSession(connectors=[agent])
    agent.ask_user("uma pergunta", correlation_id="task-1")
    session.send_message("a falar sozinho")
    assert agent.answered == []


def test_replying_to_a_local_message_is_not_routed():
    """Only messages with an origin are owed an answer."""
    agent = Agent()
    session = ChatSession(connectors=[agent])
    local = session.receive_message("mensagem local, sem origem")
    session.send_message("resposta", reply_to=local)
    assert agent.answered == []


def test_each_answer_carries_its_own_correlation():
    agent = Agent()
    session = ChatSession(connectors=[agent])
    first = agent.ask_user("primeira?", correlation_id="task-1")
    second = agent.ask_user("segunda?", correlation_id="task-2")

    session.send_message("resposta a segunda", reply_to=second)
    session.send_message("resposta a primeira", reply_to=first)

    assert agent.answered == [
        ("task-2", "resposta a segunda"),
        ("task-1", "resposta a primeira"),
    ]


def test_a_connector_that_fails_to_answer_does_not_lose_the_message():
    class Broken(Agent):
        def answer(self, correlation_id, text: str) -> None:
            raise RuntimeError("link down")

    agent = Broken()
    session = ChatSession(connectors=[agent])
    question = agent.ask_user("pergunta", correlation_id="task-1")
    session.send_message("resposta", reply_to=question)

    assert [m.text for m in session.messages] == ["pergunta", "resposta"]


def test_both_directions_coexist_on_one_connector():
    agent = Agent()
    session = ChatSession(connectors=[agent])
    assert session.ask_connector("agent", "ola") == "agent says: ola"
    question = agent.ask_user("e tu?", correlation_id="task-1")
    session.send_message("eu bem", reply_to=question)
    assert agent.asked == ["ola"]
    assert agent.answered == [("task-1", "eu bem")]


# === Lifecycle ==================================================================


def test_close_shuts_every_connector_down():
    agent, one_way = Agent(), OutboundOnly()
    session = ChatSession(connectors=[agent, one_way])
    assert agent.started is True
    session.close()
    assert agent.stopped is True


def test_one_failing_shutdown_does_not_block_the_others():
    class Stubborn(Agent):
        def shutdown(self) -> None:
            raise RuntimeError("will not stop")

    stubborn, agent = Stubborn("stubborn"), Agent("fine")
    session = ChatSession(connectors=[stubborn, agent])
    session.close()
    assert agent.stopped is True
