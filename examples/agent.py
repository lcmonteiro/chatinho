"""An agent whose tools are the chat: a lead plans, asks the coder, and answers you.

``lead`` is an ``AgentConnector``: a LangChain agent built with ``create_agent``.
Besides any tools of its own, it gets the chat as tools: ``ask_coder`` asks the
coder peer and returns its answer, and ``run_help`` runs ``/help``. Say what you
need — no ``@lead`` needed, the lead responds to what you say to everyone — and
watch it delegate: the question it puts to the coder and the coder's answer
appear in the chat, then the lead's own answer.

``coder`` is an ordinary ``OpenAIConnector``; address it directly with
``@coder <task>`` if you like.

Run it::

    export OPENAI_API_KEY=sk-...         # any OpenAI-compatible key
    python examples/agent.py

``CHATINHO_PROFILE``, ``OPENAI_BASE_URL`` and ``CHATINHO_MODEL`` work as in ``assistant.py``.
The model must support tool calling.

Needs ``pip install 'chatinho[all]'``.
"""

from chatinho import AgentConnector, Endpoint, HelpCommand, KeyUnavailable, OpenAIConnector
from chatinho import build_chat_session

LEAD    = ("You lead a small team in a terminal chat. For anything that needs code, ask the coder "
           "with the ask_coder tool, check what it wrote, then answer the user in Markdown.")
CODER   = "You are a senior Python developer. Answer with code first, then one short paragraph."
WELCOME = ("Say what you need: the lead answers, and asks the coder for any code. "
           "'@coder <task>' asks the coder directly; /help lists the commands.")


def endpoint() -> Endpoint:
    """The model to use: a profile, else ``OPENAI_*``; exits with a hint when there is no key."""
    try:
        found = Endpoint.load()
        found.check()
    except (KeyUnavailable, ValueError) as exc:
        raise SystemExit("%s; see examples/README.md" % exc)
    return found if found.model else found.with_model("gpt-4o-mini")


def parts() -> dict:
    """The lead agent, the coder it may ask, and /help."""
    model = endpoint()
    return dict(
        connectors = [
            AgentConnector("lead", model, system_prompt=LEAD, peers=["coder"]),
            OpenAIConnector("coder", model, system=CODER),
        ],
        commands   = [HelpCommand()],
        backend    = None,
    )


def main() -> None:
    """Opens the chat in the terminal."""
    build_chat_session(**parts(), title="Lead & coder", welcome_message=WELCOME, name="me").run()


if __name__ == "__main__":
    main()
