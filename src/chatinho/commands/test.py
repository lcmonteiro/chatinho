"""Test command for chatinho."""

from .base import BaseCommand
import logging
import time

logger = logging.getLogger(__name__)


class TestCommand(BaseCommand):
    """Command that runs a simple test to verify the chat is working."""
    
    def __init__(self, **kwargs):
        super().__init__(
            name="test",
            description="Executa um teste simples",
            **kwargs
        )
    
    def execute(self, chat_instance=None, **kwargs):
        """Execute the test command.
        
        Args:
            chat_instance: The chat instance (optional, for testing connectors/backend)
            **kwargs: Additional arguments
            
        Returns:
            str: Test results
        """
        logger.debug("Executing test command")
        
        results = ["=== Teste do Chatinho ==="]
        
        # Test backend if available
        if chat_instance and hasattr(chat_instance, 'backend'):
            try:
                start_time = time.time()
                test_key = f"test_{int(time.time())}"
                test_data = {"message": "Hello from chatinho!", "timestamp": time.time()}
                
                # Test save
                save_result = chat_instance.save_data(test_key, test_data)
                results.append(f"Backend save: {'✓' if save_result else '✗'}")
                
                # Test load
                loaded_data = chat_instance.load_data(test_key)
                load_result = loaded_data == test_data if loaded_data is not None else False
                results.append(f"Backend load: {'✓' if load_result else '✗'}")
                
                # Test delete
                delete_result = chat_instance.delete_data(test_key) if hasattr(chat_instance, 'delete_data') else False
                results.append(f"Backend delete: {'✓' if delete_result else '✗'}")
                
            except Exception as e:
                results.append(f"Backend test: ✗ (Erro: {e})")
                logger.error(f"Backend test failed: {e}")
        else:
            results.append("Backend: Não disponível para teste")
        
        # Test commands
        if chat_instance and hasattr(chat_instance, 'commands'):
            results.append(f"Comandos registrados: {len(chat_instance.commands)}")
            for name in chat_instance.commands.keys():
                results.append(f"  - {name}")
        else:
            results.append("Comandos: Não disponíveis para teste")
        
        # Test connectors
        if chat_instance and hasattr(chat_instance, 'connectors'):
            results.append(f"Conectores registrados: {len(chat_instance.connectors)}")
            for name in chat_instance.connectors.keys():
                results.append(f"  - {name}")
        else:
            results.append("Conectores: Não disponíveis para teste")
        
        results.append("=========================")
        return "\n".join(results)


# Keep backward compatibility with the old ChatApp style
def test_command_handler(command: str, chat_app=None):
    """Legacy handler function for backward compatibility."""
    if command == "test":
        if chat_app:
            return ("=== Teste do Chatinho ===\n"
                   "Backend: Funcional\n"
                   "Comandos: help, test\n"
                   "Conectores: Nenhum configurado\n"
                   "=========================")
        else:
            return "Teste executado com sucesso"
    return None