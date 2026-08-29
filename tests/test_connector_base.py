"""Tests for the BaseConnector contract.

``receive()`` used to be abstract with no caller anywhere in the library, so
every connector — including the two shipped ones, both examples and three test
stubs — had to write a stub returning None. It is a concrete default now.
"""

from chatinho import A2AConnector, BaseConnector, OpenAIConnector


class MinimalConnector(BaseConnector):
    """Implements only the abstract methods. It must not have to add receive()."""

    def __init__(self, name: str = "minimal") -> None:
        super().__init__(name)

    def initialize(self) -> None:
        pass

    def ask(self, message: str, **kwargs) -> str:
        return "answer: %s" % message


def test_a_connector_need_not_implement_receive():
    """Instantiating this fails with TypeError if receive() goes abstract again."""
    connector = MinimalConnector()
    assert connector.ask("ping") == "answer: ping"


def test_the_default_receive_returns_none():
    assert MinimalConnector().receive() is None


def test_the_default_receive_accepts_connector_specific_kwargs():
    assert MinimalConnector().receive(timeout=5, since="msg-1") is None


def test_the_shipped_connectors_inherit_the_default():
    """Neither is a polling transport, so neither overrides receive()."""
    for connector in (A2AConnector, OpenAIConnector):
        assert "receive" not in vars(connector)
        assert connector.receive is BaseConnector.receive


def test_initialize_and_ask_are_still_required():
    """The two methods the library does call stay abstract."""
    assert getattr(BaseConnector.initialize, "__isabstractmethod__", False) is True
    assert getattr(BaseConnector.ask, "__isabstractmethod__", False) is True
    assert getattr(BaseConnector.receive, "__isabstractmethod__", False) is False
