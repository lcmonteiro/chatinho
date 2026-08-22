"""Core chat functionality for chatinho."""

from typing import List, Dict, Any, Optional, Callable
from .connectors import BaseConnector
from .backends import BaseBackend
from .commands import BaseCommand
import logging

logger = logging.getLogger(__name__)


def create_chat(
    connectors: List[BaseConnector],
    commands: Dict[str, BaseCommand],
    backend: BaseBackend,
    title: str = "Chatinho",
    welcome_message: str = "Bem-vindo ao Chatinho!"
) -> "Chat":
    """Create a chat instance with the specified connectors, commands, and backend.
    
    Args:
        connectors: List of connector instances for external API communication
        commands: Dictionary mapping command names to command instances
        backend: Backend instance for data persistence
        title: Title of the chat application
        welcome_message: Welcome message to display on startup
        
    Returns:
        Chat: Configured chat instance
    """
    return Chat(
        connectors=connectors,
        commands=commands,
        backend=backend,
        title=title,
        welcome_message=welcome_message
    )


class Chat:
    """Main chat class that orchestrates connectors, commands, and backend."""
    
    def __init__(
        self,
        connectors: List[BaseConnector],
        commands: Dict[str, BaseCommand],
        backend: BaseBackend,
        title: str = "Chatinho",
        welcome_message: str = "Bem-vindo ao Chatinho!"
    ):
        self.connectors = {conn.name: conn for conn in connectors}
        self.commands = commands
        self.backend = backend
        self.title = title
        self.welcome_message = welcome_message
        self._initialized = False
        
        # Initialize connectors
        for connector in self.connectors.values():
            connector.initialize()
            
        # Initialize backend
        self.backend.initialize()
        
        self._initialized = True
        logger.info(f"Chat initialized with {len(self.connectors)} connectors, "
                   f"{len(self.commands)} commands, and {type(backend).__name__} backend")
    
    def run(self):
        """Start the chat application."""
        if not self._initialized:
            raise RuntimeError("Chat not properly initialized")
            
        # Display welcome message
        self._display_welcome()
        
        # Main chat loop would go here
        # For now, we'll just show that it's running
        logger.info("Chat is running...")
        print(f"{self.title} está em execução. Pressione Ctrl+C para sair.")
        
        # In a real implementation, this would start the UI/event loop
        # For demonstration, we'll just keep it simple
        try:
            while True:
                # This would normally handle user input, process messages, etc.
                # For now, just sleep to prevent immediate exit
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Chat interrompido pelo usuário")
            print("\nChat encerrado.")
    
    def _display_welcome(self):
        """Display welcome message and available commands."""
        print(f"\n{self.welcome_message}")
        print(f"Conectores disponíveis: {', '.join(self.connectors.keys())}")
        print(f"Comandos disponíveis: {', '.join(self.commands.keys())}")
        print("-" * 50)
    
    def send_message_via_connector(self, connector_name: str, message: str, **kwargs):
        """Send a message using a specific connector."""
        if connector_name not in self.connectors:
            raise ValueError(f"Connector '{connector_name}' not found")
        
        connector = self.connectors[connector_name]
        return connector.send(message, **kwargs)
    
    def execute_command(self, command_name: str, *args, **kwargs):
        """Execute a specific command."""
        if command_name not in self.commands:
            raise ValueError(f"Command '{command_name}' not found")
        
        command = self.commands[command_name]
        return command.execute(*args, **kwargs)
    
    def save_data(self, key: str, data: Any):
        """Save data using the backend."""
        return self.backend.save(key, data)
    
    def load_data(self, key: str) -> Any:
        """Load data using the backend."""
        return self.backend.load(key)