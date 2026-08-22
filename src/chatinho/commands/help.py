"""Help command for chatinho."""

from .base import BaseCommand
import logging

logger = logging.getLogger(__name__)


class HelpCommand(BaseCommand):
    """Command that displays help information about available commands."""
    
    def __init__(self, **kwargs):
        super().__init__(
            name="help",
            description="Mostra esta ajuda",
            **kwargs
        )
    
    def execute(self, chat_instance=None, **kwargs):
        """Execute the help command.
        
        Args:
            chat_instance: The chat instance (optional, for accessing commands)
            **kwargs: Additional arguments
            
        Returns:
            str: Help text
        """
        logger.debug("Executing help command")
        
        if chat_instance and hasattr(chat_instance, 'commands'):
            # If we have access to the chat instance, list all available commands
            help_text = ["Comandos disponíveis:"]
            for name, command in chat_instance.commands.items():
                help_text.append(f"  /{name} - {command.description}")
            return "\n".join(help_text)
        else:
            # Fallback help text
            return ("Comandos disponíveis:\n"
                   "  help - Mostra esta ajuda\n"
                   "  test - Executa um teste simples")


# Keep backward compatibility with the old ChatApp style
def help_command_handler(command: str, chat_app=None):
    """Legacy handler function for backward compatibility."""
    if command == "help":
        if chat_app:
            help_text = ["Comandos disponíveis:"]
            # This would need access to commands, simplified for now
            help_text.append("  help - Mostra esta ajuda")
            help_text.append("  test - Executa um teste simples")
            return "\n".join(help_text)
        else:
            return "Comandos disponíveis: help, test"
    return None