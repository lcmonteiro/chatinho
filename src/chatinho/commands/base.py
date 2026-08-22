"""Base command class for chatinho."""

from abc import ABC, abstractmethod
from typing import Any
import logging

logger = logging.getLogger(__name__)


class BaseCommand(ABC):
    """Base class for all commands."""
    
    def __init__(self, name: str, description: str = "", **kwargs):
        self.name = name
        self.description = description
        self.config = kwargs
        logger.debug(f"Initializing command '{name}': {description}")
    
    @abstractmethod
    def execute(self, *args, **kwargs) -> Any:
        """Execute the command.
        
        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            Any: Result of the command execution
        """
        pass
    
    def help(self) -> str:
        """Get help text for this command."""
        return f"{self.name}: {self.description}"