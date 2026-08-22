# Chatinho

A simple, extensible TUI chat client library built on Textual.

## Features

- Message display with Markdown rendering and syntax highlighting for code blocks.
- Input field for sending messages and commands (starting with '/').
- Ability to tag outgoing messages with an ID and match incoming replies.
- Simple in-memory message history.
- **Extensible architecture** with connectors, commands, and backends.
- Transport-agnostic: call ``receive_message`` from a worker, thread, or network callback to inject incoming messages.
- **Command Handling**: Built-in support for commands prefixed with `/` (e.g., `/help`, `/code`).
- **Command Autocomplete**: Register known commands and get a dropdown of matching suggestions as the user types `/`; Tab/Enter completes, arrows navigate, Escape dismisses.
- **Reply Threading**: Click any message to set it as the reply target; outgoing messages can be tagged as replies.
- **In-Memory History**: Full message history retained; sliding window limits rendered messages for performance.
- **Transport Agnostic**: Library does not dictate how messages are sent/received—use `send_message`, `send_command`, and `receive_message` to hook into any backend (WebSocket, HTTP, custom protocols, etc.).
- **Customizable UI**: Clean, readable theme with clear visual distinction between sent and received messages.
- **Extensible Design**: Override lifecycle hooks (`on_command`, `on_message_sent`, `on_message_received`) to inject custom logic.

## Installation

```bash
pip install chatinho
```

## Usage

### Basic Usage (Backward Compatible)

```python
from chatinho import ChatApp

app = ChatApp()
app.run()
```

### New Extensible Architecture

```python
from chatinho import create_chat
from chatinho.connectors import A2AConnector, OpenAIConnector
from chatinho.backends import DatabaseBackend
from chatinho.commands import HelpCommand, TestCommand

chat = create_chat(
    connectors=[
        A2AConnector(
            name="my_connector",
            url="https://api.example.com",
            api_key="***"
        ),
        OpenAIConnector(
            name="openai_connector",
            api_key="***"
        )
    ],
    commands=dict(
        help=HelpCommand(),
        test=TestCommand()
    ),
    backend=DatabaseBackend("sqlite:///my_database.db")
)

chat.run()
```

## Architecture

The new chatinho architecture consists of:

### Connectors
- `A2AConnector`: For communicating with Agent-to-Agent (A2A) protocol endpoints
- `OpenAIConnector`: For communicating with OpenAI API
- Base class: `BaseConnector` for creating custom connectors

### Backends
- `DatabaseBackend`: For persistent storage using SQLAlchemy
- Base class: `BaseBackend` for creating custom backends

### Commands
- `HelpCommand`: Displays available commands
- `TestCommand`: Runs a simple test to verify functionality
- Base class: `BaseCommand` for creating custom commands

## Examples

See the `examples/` directory:
- `demo.py`: Original demo showing basic functionality
- `new_usage.py`: Example of the new extensible architecture

## Running Tests

```bash
pytest
```

## License

MIT
