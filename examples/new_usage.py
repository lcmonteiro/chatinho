"""Example usage of the new chatinho architecture."""

from chatinho import create_chat
from chatinho.connectors import A2AConnector, OpenAIConnector
from chatinho.backends import DatabaseBackend
from chatinho.commands import HelpCommand, TestCommand

# Create chat instance with the desired architecture
chat = create_chat(
    connectors=[
        A2AConnector(
            name="my_connector",
            url="https://api.example.com",
            api_key="your-a2a-api-key-here"
        ),
        OpenAIConnector(
            name="openai_connector",
            api_key="your-openai-api-key-here"
        )
    ],
    commands=dict(
        help=HelpCommand(),
        test=TestCommand()
    ),
    backend=DatabaseBackend("sqlite:///my_database.db")
)

# Run the chat
if __name__ == "__main__":
    chat.run()