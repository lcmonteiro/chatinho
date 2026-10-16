"""Your chat, asking the lab on another server and lending it your key.

The lab (``lab_server.py``) appears here as one peer, ``lab``, through an
``McpConnector``. Every question you send it carries your key (your profile's,
else ``OPENAI_API_KEY``) as the ``llm`` credential; the lab answers with it and forgets it.

Run the server, then this, with the same token::

    CHATINHO_MCP_TOKEN=s3cret python examples/lab_server.py 8000
    CHATINHO_MCP_TOKEN=s3cret OPENAI_API_KEY=sk-... python examples/lab_client.py

``CHATINHO_LAB_URL`` is where the lab listens (``http://127.0.0.1:8000/mcp``).

Needs ``pip install 'chatinho[all]'``.
"""

import os

from chatinho import Endpoint, Env, HelpCommand, KeyUnavailable, McpConnector, build_chat_session

URL     = os.environ.get("CHATINHO_LAB_URL", "http://127.0.0.1:8000/mcp")
WELCOME = "Everything you write goes to the lab on %s, with your key lent for the answer."


def parts(**where) -> dict:
    """The lab as a peer, reached at *where* (``url`` and ``token`` from the environment by default).

    The key lent is the one your profile names, else ``OPENAI_API_KEY``; it is
    read again for each question, so a rotated key is lent without a restart.
    """
    try:
        found = Endpoint.load()
        found.check()
        key   = found.key
        assert key is not None                   # check() raised otherwise
        where = where or dict(url=URL, token=Env("CHATINHO_MCP_TOKEN"))
        lab   = McpConnector(**where, name="lab", delegate={"llm": key})
    except (KeyUnavailable, ValueError) as exc:
        raise SystemExit("%s; see examples/README.md" % exc)
    return dict(connectors=[lab], commands=[HelpCommand()], backend=None)


def main() -> None:
    """Opens the chat in the terminal."""
    build_chat_session(**parts(), title="Lab client", welcome_message=WELCOME % URL, name="me").run()


if __name__ == "__main__":
    main()
