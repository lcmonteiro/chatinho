"""Base connector class for chatinho."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
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
    
    @abstractmethod
    def receive(self, **kwargs) -> Any:
        """Receive a message from this connector.
        
        Args:
            **kwargs: Additional connector-specific parameters
            
        Returns:
            Any: Received message or data
        """
        pass