"""Base backend class for chatinho."""

from abc import ABC, abstractmethod
from typing import Any, Optional
import logging

logger = logging.getLogger(__name__)


class BaseBackend(ABC):
    """Base class for all backends."""
    
    def __init__(self, **kwargs):
        self.config = kwargs
        logger.debug(f"Initializing backend with config: {kwargs}")
    
    @abstractmethod
    def initialize(self):
        """Initialize the backend. Called during chat setup."""
        pass
    
    @abstractmethod
    def save(self, key: str, data: Any) -> bool:
        """Save data with the given key.
        
        Args:
            key: Identifier for the data
            data: Data to save
            
        Returns:
            bool: True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def load(self, key: str) -> Any:
        """Load data by key.
        
        Args:
            key: Identifier for the data
            
        Returns:
            Any: The saved data, or None if not found
        """
        pass
    
    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete data by key.
        
        Args:
            key: Identifier for the data
            
        Returns:
            bool: True if successful, False otherwise
        """
        pass