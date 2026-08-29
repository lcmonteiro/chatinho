"""Tests for the BaseConnector contract.

``receive()`` used to be abstract with no caller anywhere in the library, so
every connector — including the two shipped ones, both examples and three test
stubs — had to write a stub returning None. It is a concrete default now.
"""

from chatinho import A2AConnector, BaseConnector, OpenAIConnector


class SendOnlyConnector(BaseConnector):
    """A connector that only sends. It must not have to implement receive()."""

    def __init__(self, name: str = "send-only") -> None:
        super().__init__(name)

    def initialize(self) -> None:
        pass

    def send(self, message: str, **kwargs) -> str:
        return "sent: %s" % message


def test_a_connector_need_not_implement_receive():
    """Instantiating this fails with TypeError if receive() goes abstract again."""
    connector = SendOnlyConnector()
    assert connector.send("ping") == "sent: ping"


def test_the_default_receive_returns_none():
    assert SendOnlyConnector().receive() is None


def test_the_default_receive_accepts_connector_specific_kwargs():
    assert SendOnlyConnector().receive(timeout=5, since="msg-1") is None


def test_the_shipped_connectors_inherit_the_default():
    """Neither is a polling transport, so neither overrides receive()."""
    for connector in (A2AConnector, OpenAIConnector):
        assert "receive" not in vars(connector)
        assert connector.receive is BaseConnector.receive


def test_initialize_and_send_are_still_required():
    """The two methods the library does call stay abstract."""
    assert getattr(BaseConnector.initialize, "__isabstractmethod__", False) is True
    assert getattr(BaseConnector.send, "__isabstractmethod__", False) is True
    assert getattr(BaseConnector.receive, "__isabstractmethod__", False) is False
