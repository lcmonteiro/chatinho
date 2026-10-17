"""
A terminal assistant that remembers: ask a model, close the chat, come back tomorrow.

One ``OpenAIConnector`` answers everything you type. The conversation is kept in
a SQLite file, so the next run reopens it and the model still has it as history.
Markdown and code blocks in the answers are rendered by the terminal.

Run it::

    export OPENAI_API_KEY=sk-...         # any OpenAI-compatible key
    python examples/assistant.py

``CHATINHO_PROFILE`` picks a profile from your profiles file (endpoint, model
and where the key is; see ``examples/README.md``). Without one, ``OPENAI_API_KEY``,
``OPENAI_BASE_URL`` and ``CHATINHO_MODEL`` (``gpt-4o-mini`` by default) are used.
``CHATINHO_DB`` the file the conversation is kept in (``assistant.db``; delete it
to start fresh).

Needs ``pip install 'chatinho[all]'``.
"""

import os

from chatinho import DatabaseBackend, Endpoint, HelpCommand, KeyUnavailable, OpenAIConnector
from chatinho import build_chat_session

SYSTEM  = "You are a concise, helpful assistant in a terminal chat. Answer in Markdown."
WELCOME = "Ask anything. The conversation is kept, so you can pick it up next time. /help lists the commands."


def endpoint() -> Endpoint:
    """The model to use: a profile, else ``OPENAI_*``; exits with a hint when there is no key."""
    try:
        found = Endpoint.load()
        found.check()
    except (KeyUnavailable, ValueError) as exc:
        raise SystemExit("%s; see examples/README.md" % exc)
    return found if found.model else found.with_model("gpt-4o-mini")


def parts() -> dict:
    """What the chat is made of: the assistant, /help, and the database that remembers."""
    return dict(
        connectors = [OpenAIConnector("assistant", endpoint(), system=SYSTEM)],
        commands   = [HelpCommand()],
        backend    = DatabaseBackend("sqlite:///%s" % os.environ.get("CHATINHO_DB", "assistant.db")),
    )


def main() -> None:
    """Opens the chat in the terminal."""
    build_chat_session(**parts(), title="Assistant", welcome_message=WELCOME, name="me").run()


if __name__ == "__main__":
    main()
