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
- **Extensible Design**: Assign lifecycle hooks (`on_command`, `on_message_sent`, `on_message_received`) on the chat returned by `create_chat` to inject custom logic.

## Installation

```bash
pip install chatinho
```

## Usage

### Basic Usage

```python
from chatinho import create_chat

chat = create_chat()
chat.run()
```

`create_chat` is the only entry point for the terminal app: the application class
itself is private, and connectors, commands and a backend are all optional.

For a chat without a terminal — a script, a bot, a test — use `ChatSession`, which
holds the same use cases and imports no UI framework:

```python
from chatinho import ChatSession, HelpCommand

session = ChatSession(commands={"help": HelpCommand()})
session.on_message_added = lambda msg: print(msg.text)
session.send_command("help")
```

### Full Architecture

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

The chatinho architecture consists of:

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
- `demo.py`: Full demo showing Markdown rendering, code blocks, commands and replies

## Running Tests

```bash
pytest
```

## License

MIT
