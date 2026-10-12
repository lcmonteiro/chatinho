"""Two models in one room: a coder writes, a reviewer reads everything and critiques.

Both are ``OpenAIConnector`` peers with their own system prompt. Address one by
name — ``@coder write a function that…`` then ``@reviewer what would you
change?``. The coder remembers only its own exchanges; the reviewer's memory is
the whole room, so it sees what the coder wrote, prefixed ``coder:``.

Run it::

    export OPENAI_API_KEY=sk-...         # any OpenAI-compatible key
    python examples/team.py

``OPENAI_BASE_URL`` and ``CHATINHO_MODEL`` work as in ``assistant.py``.

Needs ``pip install 'chatinho[all]'``.
"""

import os

from chatinho import HelpCommand, OpenAIConnector, Query, build_chat_session

CODER    = "You are a senior Python developer. Answer with code first, then one short paragraph."
REVIEWER = ("You are a strict code reviewer. Lines prefixed 'coder:' were written by a colleague. "
            "Point out bugs, risks and simpler alternatives, as a short list.")
WELCOME  = ("Two peers are here. Write '@coder <task>' to ask for code, "
            "then '@reviewer <question>' for a review of what the coder wrote.")


def config() -> dict:
    """The model settings, from the environment; exits with a hint when there is no key."""
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise SystemExit("set OPENAI_API_KEY (any OpenAI-compatible key); see examples/README.md")
    return dict(api_key=key, base_url=os.environ.get("OPENAI_BASE_URL") or None,
                model=os.environ.get("CHATINHO_MODEL", "gpt-4o-mini"))


def parts() -> dict:
    """The coder, the reviewer who sees the whole room, and /help."""
    settings = config()
    return dict(
        connectors = [
            OpenAIConnector(name="coder", system=CODER, **settings),
            OpenAIConnector(name="reviewer", system=REVIEWER,
                            memory=Query(errors=False).last(30), **settings),
        ],
        commands   = [HelpCommand()],
        backend    = None,
    )


def main() -> None:
    """Opens the room in the terminal."""
    build_chat_session(**parts(), title="Coder & reviewer", welcome_message=WELCOME, name="me").run()


if __name__ == "__main__":
    main()
