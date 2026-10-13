"""Two models in one room: a coder writes, a reviewer reads everything and critiques.

Both are ``OpenAIConnector`` peers with their own system prompt. Address one by
name — ``@coder write a function that…`` then ``@reviewer what would you
change?``. The coder remembers only its own exchanges; the reviewer's memory is
the whole room, so it sees what the coder wrote, prefixed ``coder:``.

Run it::

    export OPENAI_API_KEY=sk-...         # any OpenAI-compatible key
    python examples/team.py

``CHATINHO_PROFILE``, ``OPENAI_BASE_URL`` and ``CHATINHO_MODEL`` work as in ``assistant.py``.

Needs ``pip install 'chatinho[all]'``.
"""

from chatinho import Endpoint, HelpCommand, KeyUnavailable, OpenAIConnector, Query, build_chat_session

CODER    = "You are a senior Python developer. Answer with code first, then one short paragraph."
REVIEWER = ("You are a strict code reviewer. Lines prefixed 'coder:' were written by a colleague. "
            "Point out bugs, risks and simpler alternatives, as a short list.")
WELCOME  = ("Two peers are here. Write '@coder <task>' to ask for code, "
            "then '@reviewer <question>' for a review of what the coder wrote.")


def endpoint() -> Endpoint:
    """The model to use: a profile, else ``OPENAI_*``; exits with a hint when there is no key."""
    try:
        found = Endpoint.load()
        found.check()
    except (KeyUnavailable, ValueError) as exc:
        raise SystemExit("%s; see examples/README.md" % exc)
    return found if found.model else found.with_model("gpt-4o-mini")


def parts() -> dict:
    """The coder, the reviewer who sees the whole room, and /help."""
    model = endpoint()
    return dict(
        connectors = [
            OpenAIConnector("coder", model, system=CODER),
            OpenAIConnector("reviewer", model, system=REVIEWER, memory=Query(errors=False).last(30)),
        ],
        commands   = [HelpCommand()],
        backend    = None,
    )


def main() -> None:
    """Opens the room in the terminal."""
    build_chat_session(**parts(), title="Coder & reviewer", welcome_message=WELCOME, name="me").run()


if __name__ == "__main__":
    main()
