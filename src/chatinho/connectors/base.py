"""Base connector class for chatinho."""

from abc import ABC, abstractmethod
from typing import Any, Callable, Optional
import logging

logger = logging.getLogger(__name__)

# What a connector calls to put an agent's question in front of the user:
# ``inbox(text, correlation_id) -> message id``. The session supplies it in
# ``attach``. The id is an opaque handle the connector can hold on to; the
# routing itself works off the correlation id, not this.
Inbox = Callable[[str, Optional[str]], str]


class BaseConnector(ABC):
    """A link between the user and an agent or API.

    This base is the outbound half: the user asks, the far side answers. A
    connector whose far side can also start the conversation extends
    :class:`BidirectionalConnector` instead.
    """
    
    def __init__(self, name: str, **kwargs):
        self.name = name
        self.config = kwargs
        logger.debug(f"Initializing connector '{name}' with config: {kwargs}")
    
    @abstractmethod
    def initialize(self):
        """Initialize the connector. Called during chat setup."""
        pass
    
    @abstractmethod
    def ask(self, message: str, **kwargs) -> Any:
        """Send a message to the external service and return its answer.

        Named ``ask`` rather than ``send`` because it is a request/response
        exchange, not a one-way write: every implementation returns what came
        back, and callers feed that straight into the chat as an incoming
        message. A one-way transport would be a different interface.

        Args:
            message: The message to send
            **kwargs: Additional connector-specific parameters

        Returns:
            Any: Response from the external service
        """
        pass
    
    def receive(self, **kwargs) -> Any:
        """Poll this connector for an incoming message.

        Not abstract: nothing in the library calls it, and every connector
        written so far is request/response, so requiring an implementation only
        forced each of them to write a stub returning None. Override it in a
        connector that genuinely polls — a webhook queue, a socket — and drive
        it from your own loop.

        Args:
            **kwargs: Additional connector-specific parameters

        Returns:
            Any: Received message or data; None when there is nothing to poll.
        """
        return None

    def shutdown(self) -> None:
        """Release whatever :meth:`initialize` acquired.

        Not abstract: most connectors hold nothing but an HTTP client. Override
        it in one that owns a socket, a thread or a server — the session calls
        this for every connector in :meth:`~chatinho.chat_session.ChatSession.close`.
        """


class BidirectionalConnector(BaseConnector):
    """A connector whose far side can also start the conversation.

    The connector brings its own listener — a small server, a poll loop, a
    subscription — and calls :meth:`ask_user` when a question arrives. The
    user's reply comes back through :meth:`answer`.

    Direction is declared by type, not by a flag: a connector that only ever
    speaks outbound stays a plain :class:`BaseConnector` and is never asked to
    implement any of this.
    """

    def __init__(self, name: str, **kwargs):
        super().__init__(name, **kwargs)
        self._inbox: Optional[Inbox] = None

    def attach(self, inbox: Inbox) -> None:
        """Receives the callable that puts a question in front of the user.

        Called by the session when the connector is registered. The connector
        depends on this callable, not on the session — which is what keeps the
        dependency pointing inwards.

        Args:
            inbox: Called as ``inbox(text, correlation_id)``.
        """
        self._inbox = inbox

    def ask_user(self, text: str, correlation_id: Optional[str] = None) -> str:
        """Puts the far side's question in front of the user.

        Call this from the connector's listener. Safe to call from another
        thread: a presentation layer marshals the update itself.

        Args:
            text: The question, as the user should see it.
            correlation_id: The far side's own id for this exchange (an A2A
                ``taskId``, a request id); handed back to :meth:`answer`.

        Returns:
            str: The id of the message the question became.

        Raises:
            RuntimeError: If the connector was never registered with a chat.
        """
        if self._inbox is None:
            raise RuntimeError(
                "Connector '%s' is not attached to a chat: register it with "
                "add_connector() before delivering messages" % self.name
            )
        return self._inbox(text, correlation_id)

    @abstractmethod
    def answer(self, correlation_id: Optional[str], text: str) -> None:
        """Sends the user's reply back to whoever asked.

        Args:
            correlation_id: The value handed to :meth:`ask_user`, or None when
                the exchange carries no correlation.
            text: What the user replied.
        """