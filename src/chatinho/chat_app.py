"""Merged chat application with hook-based connector system.

This file implements:
- Base classes for connectors, commands, backend
- Hook system where connectors declare which events they handle via decorators
- Mock components for demonstration
- Chat logic that orchestrates connectors, commands, backend and triggers hooks
- Terminal UI (Textual) that interacts with the chat system
- Demo section that creates chat with mock components and runs the UI
"""

import logging
import threading
import time
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Dict, List, Optional, Tuple, Any, Set

from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, ScrollableContainer, Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Input, Markdown, OptionList, Static
from textual.widgets.option_list import Option

logger = logging.getLogger(__name__)

# === Hook System ===

# Define hook point constants
HOOK_MESSAGE_SENT = "message_sent"
HOOK_MESSAGE_RECEIVED = "message_received"
HOOK_COMMAND_EXECUTED = "command_executed"
HOOK_CONNECTOR_ADDED = "connector_added"
HOOK_BACKEND_SAVE = "backend_save"
HOOK_BACKEND_LOAD = "backend_load"

ALL_HOOKS = {
    HOOK_MESSAGE_SENT,
    HOOK_MESSAGE_RECEIVED,
    HOOK_COMMAND_EXECUTED,
    HOOK_CONNECTOR_ADDED,
    HOOK_BACKEND_SAVE,
    HOOK_BACKEND_LOAD,
}

def hook_point(*event_names):
    """
    Decorator to mark a connector class with the hook points it handles.
    
    Usage:
        @hook_point(HOOK_MESSAGE_SENT, HOOK_MESSAGE_RECEIVED)
        class MyConnector(BaseConnector):
            def on_message_sent(self, message): ...
            def on_message_received(self, message): ...
    """
    def decorator(cls):
        # Store the hook points this connector handles
        if not hasattr(cls, '_hook_points'):
            cls._hook_points = set()
        cls._hook_points.update(event_names)
        return cls
    return decorator

# === Base Classes (minimal interfaces) ===

class BaseConnector:
    """Base class for transport connectors."""
    def __init__(self, name: str = "unnamed"):
        self.name = name
    
    def initialize(self) -> None:
        """Called when the connector is added to a chat."""
        pass
    
    # Optional hook methods - connectors can implement those they care about
    def on_message_sent(self, message: str, **kwargs) -> None:
        """Called when a message is sent via the chat."""
        pass
    
    def on_message_received(self, message: str, **kwargs) -> None:
        """Called when a message is received (to be displayed)."""
        pass
    
    def on_command_executed(self, command: str, result: Any, **kwargs) -> None:
        """Called when a command is executed."""
        pass
    
    def on_connector_added(self, chat: 'Chat', **kwargs) -> None:
        """Called when this connector is added to a chat."""
        pass
    
    def on_backend_save(self, key: str, data: Any, **kwargs) -> None:
        """Called when data is saved to the backend."""
        pass
    
    def on_backend_load(self, key: str, data: Any, **kwargs) -> None:
        """Called when data is loaded from the backend."""
        pass
    
    # Core transport methods (to be implemented by subclasses)
    def send(self, message: str, **kwargs) -> Any:
        """Send a message via this connector. Should return success indicator."""
        raise NotImplementedError
    
    def receive(self) -> Optional[str]:
        """Check for incoming messages. Returns message string or None."""
        raise NotImplementedError

class BaseCommand:
    """Base class for chat commands."""
    def execute(self, *args, **kwargs) -> Any:
        """Execute the command and return result."""
        raise NotImplementedError

class BaseBackend:
    """Base class for data persistence."""
    def __init__(self):
        pass
    
    def initialize(self) -> None:
        """Called when the backend is initialized."""
        pass
    
    def save(self, key: str, data: Any) -> None:
        """Save data. Should raise exception on failure."""
        raise NotImplementedError
    
    def load(self, key: str) -> Any:
        """Load data. Returns None if key not found."""
        raise NotImplementedError

# === Mock Components for Demo ===

@hook_point(HOOK_MESSAGE_SENT, HOOK_MESSAGE_RECEIVED)
class MockTransportConnector(BaseConnector):
    """Mock connector that simulates sending/receiving messages with hook integration."""
    def __init__(self, name: str = "mock"):
        super().__init__(name)
        self._messages: List[str] = []  # Simulate received messages (echo)
        self._chat: Optional['Chat'] = None  # Reference to chat for triggering hooks
    
    def initialize(self) -> None:
        logger.info(f"MockTransportConnector '{self.name}' initialized")
        # Trigger connector added hook if chat is set
        if self._chat:
            self._chat._trigger_hook(HOOK_CONNECTOR_ADDED, connector=self)
    
    def set_chat(self, chat: 'Chat') -> None:
        """Set the chat reference for hook triggering."""
        self._chat = chat
    
    def send(self, message: str, **kwargs) -> bool:
        """Simulate sending a message; store it as if received (echo)."""
        logger.info(f"MockTransportConnector sending: {message}")
        # Simulate network delay
        time.sleep(0.1)
        # Store as received message (echo)
        self._messages.append(message)
        # Trigger message sent hook via chat (if chat reference exists)
        if self._chat:
            self._chat._trigger_hook(HOOK_MESSAGE_SENT, message=message, connector=self)
        return True
    
    def receive(self) -> Optional[str]:
        """Check for any received messages."""
        if self._messages:
            msg = self._messages.pop(0)
            # Trigger message received hook via chat
            if self._chat:
                self._chat._trigger_hook(HOOK_MESSAGE_RECEIVED, message=msg, connector=self)
            return msg
        return None

@hook_point(HOOK_COMMAND_EXECUTED)
class MockHelpCommand(BaseCommand):
    """Mock help command."""
    def execute(self, *args, **kwargs) -> str:
        result = "Available commands: help, test\nType /help or /test"
        logger.info(f"Help command executed: {result}")
        return result

@hook_point(HOOK_COMMAND_EXECUTED)
class MockTestCommand(BaseCommand):
    """Mock test command."""
    def execute(self, *args, **kwargs) -> str:
        result = "Test command executed successfully!"
        logger.info(f"Test command executed: {result}")
        return result

class DatabaseBackend(BaseBackend):
    """Simple SQLite backend for demo with hook support."""
    def __init__(self, db_url: str = "sqlite:///my_database.db"):
        # Extract filename from URL (simple parsing)
        if db_url.startswith("sqlite:///"):
            prefix = "sqlite:///"
            self.db_file = db_url[len(prefix):]
            # If the path starts with '/', remove it to make it relative (as SQLAlchemy does)
            if self.db_file.startswith('/'):
                self.db_file = self.db_file[1:]
            logger.info(f"DatabaseBackend: db_url={db_url}, prefix={prefix}, db_file={self.db_file}")
        else:
            self.db_file = "chat_demo.db"
            logger.info(f"DatabaseBackend: using default db_file={self.db_file}")
        self.conn: Optional[sqlite3.Connection] = None
        self._chat: Optional['Chat'] = None
    
    def set_chat(self, chat: 'Chat') -> None:
        """Set the chat reference for hook triggering."""
        self._chat = chat
    
    def initialize(self) -> None:
        # Ensure directory exists if there is a directory component
        import os
        db_dir = os.path.dirname(self.db_file)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        # Log the db file we are trying to open
        logger.info(f"Attempting to open SQLite database at: {self.db_file}")
        try:
            self.conn = sqlite3.connect(self.db_file)
        except sqlite3.OperationalError as e:
            logger.error(f"Failed to connect to database at {self.db_file}: {e}")
            # Try to create the file and try again
            try:
                # Ensure the directory exists
                if db_dir:
                    os.makedirs(db_dir, exist_ok=True)
                # Touch the file
                open(self.db_file, 'a').close()
                self.conn = sqlite3.connect(self.db_file)
                logger.info(f"Successfully connected after touching file: {self.db_file}")
            except Exception as e2:
                logger.error(f"Second attempt also failed: {e2}")
                raise
        # Create table if not exists
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_data (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        self.conn.commit()
        logger.info(f"DatabaseBackend initialized with {self.db_file}")
        # Trigger backend initialized hook (if we had one)
        if self._chat:
            self._chat._trigger_hook(HOOK_CONNECTOR_ADDED, backend=self)  # Reusing for now
    
    def save(self, key: str, data: Any) -> None:
        if self.conn is None:
            raise RuntimeError("Backend not initialized")
        value = str(data)  # Simple storage as string
        self.conn.execute(
            "INSERT OR REPLACE INTO chat_data (key, value) VALUES (?, ?)",
            (key, value)
        )
        self.conn.commit()
        logger.debug(f"Saved {key}: {value}")
        # Trigger backend save hook
        if self._chat:
            self._chat._trigger_hook(HOOK_BACKEND_SAVE, key=key, data=value, backend=self)
    
    def load(self, key: str) -> Any:
        if self.conn is None:
            raise RuntimeError("Backend not initialized")
        cursor = self.conn.execute(
            "SELECT value FROM chat_data WHERE key = ?", (key,)
        )
        row = cursor.fetchone()
        if row is None:
            return None
        value = row[0]  # Return as string
        logger.debug(f"Loaded {key}: {value}")
        # Trigger backend load hook
        if self._chat:
            self._chat._trigger_hook(HOOK_BACKEND_LOAD, key=key, data=value, backend=self)
        return value

# === Chat Logic (with hook system) ===

def create_chat(
    connectors: List[BaseConnector],
    commands: Dict[str, BaseCommand],
    backend: BaseBackend,
    title: str = "Chatinho",
    welcome_message: str = "Bem-vindo ao Chatinho!"
) -> "Chat":
    """Create a chat instance with the specified connectors, commands, and backend."""
    return Chat(
        connectors=connectors,
        commands=commands,
        backend=backend,
        title=title,
        welcome_message=welcome_message
    )


class Chat(App):
    """Main chat application built with Textual, integrating chat logic and UI."""
    
    CSS = """
    .message-bubble {
        background: $boost;
        color: $text;
        padding: 1 2;
    }
    .message-header {
        text-style: dim;
    }
    .message-quote {
        text-style: italic;
        color: $text-muted;
    }
    .sent {
        align: right middle;
    }
    .received {
        align: left middle;
    }
    .reply-target {
        background: $accent;
    }
    """

    def __init__(
        self,
        connectors: List[BaseConnector],
        commands: Dict[str, BaseCommand],
        backend: BaseBackend,
        title: str = "Chatinho",
        welcome_message: str = "Bem-vindo ao Chatinho!",
        max_displayed: int = 100,
    ) -> None:
        super().__init__()
        
        # Logic components
        self.connectors: Dict[str, BaseConnector] = {}
        self.commands = commands
        self.backend = backend
        self.title = title
        self.welcome_message = welcome_message
        self._initialized = False
        
        # Hook registry: maps hook name to list of connectors that handle it
        self._hook_registry: Dict[str, List[BaseConnector]] = {hook: [] for hook in ALL_HOOKS}
        
        # Initialize connectors (this will register them for hooks)
        for connector in connectors:
            self.add_connector(connector)
            
        # Initialize backend
        self.backend.initialize()
        # Set chat reference on backend for hook triggering
        if hasattr(self.backend, 'set_chat'):
            self.backend.set_chat(self)
        
        # UI state
        self.messages  : List[ChatMessage] = []
        self._next_id  : int = 1
        self._id_lock  : threading.Lock = threading.Lock()
        self._replies  : Dict[str, List[str]] = {}
        self._replies_lock : threading.Lock = threading.Lock()
        self._reply_target : Optional[str] = None
        self._msg_widgets  : Dict[str, Widget] = {}
        self._msg_index    : Dict[str, ChatMessage] = {}
        self._input_placeholder = "Type a message or /command"
        self.max_displayed: int = max_displayed
        self._rendered_msg_ids: List[str] = []
        self._app_thread_id: Optional[int] = None
        
        self._initialized = True
        logger.info(f"Chat initialized with {len(self.connectors)} connectors, "
                   f"{len(self.commands)} commands, and {type(backend).__name__} backend")
    
    # === Hook triggering methods ===
    
    def _trigger_hook(self, hook_name: str, **kwargs) -> None:
        """
        Trigger all connectors registered for a given hook.
        
        Args:
            hook_name: The hook constant to trigger
            **kwargs: Arguments to pass to the hook methods
        """
        if hook_name not in ALL_HOOKS:
            logger.warning(f"Unknown hook name: {hook_name}")
            return
        
        connectors = self._hook_registry.get(hook_name, [])
        if not connectors:
            logger.debug(f"No connectors registered for hook '{hook_name}'")
            return
        
        logger.debug(f"Triggering hook '{hook_name}' on {len(connectors)} connector(s)")
        
        for connector in connectors:
            try:
                # Determine which method to call based on hook name
                method_map = {
                    HOOK_MESSAGE_SENT: 'on_message_sent',
                    HOOK_MESSAGE_RECEIVED: 'on_message_received',
                    HOOK_COMMAND_EXECUTED: 'on_command_executed',
                    HOOK_CONNECTOR_ADDED: 'on_connector_added',
                    HOOK_BACKEND_SAVE: 'on_backend_save',
                    HOOK_BACKEND_LOAD: 'on_backend_load',
                }
                
                method_name = method_map.get(hook_name)
                if method_name and hasattr(connector, method_name):
                    method = getattr(connector, method_name)
                    method(**kwargs)
                else:
                    logger.debug(f"Connector {connector.name} does not implement {method_name}")
                    
            except Exception as e:
                logger.error(f"Error in hook '{hook_name}' for connector {connector.name}: {e}", exc_info=True)
    
    # === Public API (modified to trigger hooks) ===
    
    def send_message_via_connector(self, connector_name: str, message: str, **kwargs):
        """Send a message using a specific connector and trigger message sent hook."""
        if connector_name not in self.connectors:
            raise ValueError(f"Connector '{connector_name}' not found")
        
        connector = self.connectors[connector_name]
        result = connector.send(message, **kwargs)
        # Note: The connector's send method already triggers HOOK_MESSAGE_SENT via its internal logic
        # But we can also trigger it here if needed for centralized handling
        # self._trigger_hook(HOOK_MESSAGE_SENT, message=message, connector=connector, result=result)
        return result
    
    def execute_command(self, command_name: str, *args, **kwargs):
        """Execute a specific command and trigger command executed hook."""
        if command_name not in self.commands:
            raise ValueError(f"Command '{command_name}' not found")
        
        command = self.commands[command_name]
        try:
            result = command.execute(*args, **kwargs)
            # Trigger command executed hook
            self._trigger_hook(HOOK_COMMAND_EXECUTED, command=command_name, result=result, args=args, kwargs=kwargs)
            return result
        except Exception as e:
            logger.error(f"Error executing command '{command_name}': {e}")
            # Still trigger hook with error info?
            self._trigger_hook(HOOK_COMMAND_EXECUTED, command=command_name, error=e, args=args, kwargs=kwargs)
            raise
    
    def save_data(self, key: str, data: Any):
        """Save data using the backend and trigger backend save hook."""
        self.backend.save(key, data)
        # Note: The backend's save method already triggers HOOK_BACKEND_SAVE via its internal logic
    
    def load_data(self, key: str) -> Any:
        """Load data using the backend and trigger backend load hook."""
        result = self.backend.load(key)
        # Note: The backend's load method already triggers HOOK_BACKEND_LOAD via its internal logic
        return result


# === Terminal UI (ChatApp, integrated with hook system) ===

COMMAND_PREFIX : str = "/"


class TouchScrollableContainer(ScrollableContainer):
    """Scrollable container that supports mouse/touch drag scrolling."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._drag_start_y: int = 0
        self._scroll_start_y: int = 0

    def on_mouse_down(self, event: events.MouseDown) -> None:
        """Record the start position when drag begins."""
        self._drag_start_y = event.y
        self._scroll_start_y = self.scroll_offset.y
        event.stop()

    def on_mouse_move(self, event: events.MouseMove) -> None:
        """Handle drag to scroll vertically."""
        if not event.button:
            return
        delta_y = event.y - self._drag_start_y
        target_y = self._scroll_start_y - delta_y
        max_y = self.max_scroll_y
        if max_y > 0:
            target_y = max(0, min(target_y, max_y))
            self.scroll_to(y=target_y, animate=False)
        event.stop()

    def on_mouse_up(self, event: events.MouseUp) -> None:
        """Handle drag end."""
        event.stop()


@dataclass
class ChatMessage:
    """Represents a chat message."""

    id          : str
    text        : str
    timestamp   : datetime = field(default_factory=datetime.now)
    is_command  : bool = False
    reply_to    : Optional[str] = None
    is_sent_by_me : bool = True


# === Demo Section ===

if __name__ == "__main__":
    # Configure logging for demo
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    
    # Create chat with mock components as per user's example
    chat = Chat(
        connectors=[
            MockTransportConnector()
        ],
        commands=dict(
            help=MockHelpCommand(),
            test=MockTestCommand()
        ),
        backend=DatabaseBackend("sqlite:///my_database.db")
    )

    # Run the chat (starts UI)
    chat.run()