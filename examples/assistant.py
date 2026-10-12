"""A terminal assistant that remembers: ask a model, close the chat, come back tomorrow.

One ``OpenAIConnector`` answers everything you type. The conversation is kept in
a SQLite file, so the next run reopens it and the model still has it as history.
Markdown and code blocks in the answers are rendered by the terminal.

Run it::

    export OPENAI_API_KEY=sk-...         # any OpenAI-compatible key
    python examples/assistant.py

``OPENAI_BASE_URL`` points it at another endpoint (Ollama, OpenRouter, Azure, …),
``CHATINHO_MODEL`` picks the model (``gpt-4o-mini`` by default) and
``CHATINHO_DB`` the file the conversation is kept in (``assistant.db``; delete it
to start fresh).

Needs ``pip install 'chatinho[all]'``.
"""

import os

from chatinho import DatabaseBackend, HelpCommand, OpenAIConnector, build_chat_session

SYSTEM  = "You are a concise, helpful assistant in a terminal chat. Answer in Markdown."
WELCOME = "Ask anything. The conversation is kept, so you can pick it up next time. /help lists the commands."


def config() -> dict:
    """The model settings, from the environment; exits with a hint when there is no key."""
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise SystemExit("set OPENAI_API_KEY (any OpenAI-compatible key); see examples/README.md")
    return dict(api_key=key, base_url=os.environ.get("OPENAI_BASE_URL") or None,
                model=os.environ.get("CHATINHO_MODEL", "gpt-4o-mini"))


def parts() -> dict:
    """What the chat is made of: the assistant, /help, and the database that remembers."""
    return dict(
        connectors = [OpenAIConnector(name="assistant", system=SYSTEM, **config())],
        commands   = [HelpCommand()],
        backend    = DatabaseBackend("sqlite:///%s" % os.environ.get("CHATINHO_DB", "assistant.db")),
    )


def main() -> None:
    """Opens the chat in the terminal."""
    build_chat_session(**parts(), title="Assistant", welcome_message=WELCOME, name="me").run()


if __name__ == "__main__":
    main()
