"""Base connector class for chatinho."""

from abc import ABC, abstractmethod
from typing import Any
import logging

logger = logging.getLogger(__name__)


class BaseConnector(ABC):
    """Base class for all connectors."""
    
    def __init__(self, name: str, **kwargs):
        self.name = name
        self.config = kwargs
        logger.debug(f"Initializing connector '{name}' with config: {kwargs}")
    
    @abstractmethod
    def initialize(self):
        """Initialize the connector. Called during chat setup."""
        pass
    
    @abstractmethod
    def send(self, message: str, **kwargs) -> Any:
        """Send a message through this connector.
        
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