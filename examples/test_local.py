"""Local test of chatinho architecture without external dependencies."""

from chatinho import create_chat
from chatinho.commands import HelpCommand, TestCommand
from chatinho.backends import DatabaseBackend

# Test with no external connectors - just to verify the architecture works
print("=== Testando arquitetura chatinho localmente ===")
print("Criando chat com comandos apenas (sem conectores externos)...")

try:
    chat = create_chat(
        connectors=[],  # Lista vazia - sem conectores externos
        commands=dict(
            help=HelpCommand(),
            test=TestCommand()
        ),
        # Usando banco em memória para teste rápido
        backend=DatabaseBackend("sqlite:///:memory:")
    )
    print("✓ Chat criado com sucesso!")
    
    # Testando comandos
    print("\n--- Testando comando 'help' ---")
    help_result = chat.execute_command('help')
    print(help_result)
    
    print("\n--- Testando comando 'test' ---")
    test_result = chat.execute_command('test')
    print(test_result)
    
    print("\n=== Arquitetura funcionando corretamente! ===")
    print("Os conectores A2A e OpenAI podem ser adicionados quando você tiver:")
    print("  - Uma URL válida de endpoint A2A")
    print("  - Uma API key válida da OpenAI")
    
except Exception as e:
    print(f"✗ Erro: {e}")
    import traceback
    traceback.print_exc()
