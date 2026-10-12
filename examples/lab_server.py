"""A model served over MCP, with no key of its own: whoever asks lends theirs.

``build_mcp_session`` serves one ``OpenAIConnector``, ``lab``, over Streamable
HTTP behind a bearer token. The server holds no API key. It declares the ``llm``
credential, a client delegates its own key with each question, and the lab
answers with it — for that message only, without keeping or logging it.

Run it::

    CHATINHO_MCP_TOKEN=s3cret python examples/lab_server.py 8000

then ask it from a chat (``lab_client.py``) or any MCP client
(``lab_fastmcp_client.py``). ``CHATINHO_PROFILE``, ``OPENAI_BASE_URL`` and
``CHATINHO_MODEL`` work as in ``assistant.py``; no key is read here, even if the
profile names one.

Needs ``pip install 'chatinho[all]'``.
"""

import os
import sys

from chatinho import Endpoint, OpenAIConnector, build_mcp_session

SYSTEM      = "You are a research assistant answering other agents. Be precise and brief."
CREDENTIALS = {"llm": "OpenAI-compatible API key"}


def parts() -> dict:
    """The lab: a model with no key, answering with the one each question lends."""
    found = Endpoint.load().without_key()
    lab   = OpenAIConnector(name="lab", system=SYSTEM, endpoint=found, model=found.model or "gpt-4o-mini")
    return dict(connectors=[lab], commands=[], backend=None)


def main() -> None:
    """Serves the lab on the port given, 8000 by default."""
    token = os.environ.get("CHATINHO_MCP_TOKEN")
    if not token:
        raise SystemExit("set CHATINHO_MCP_TOKEN, the bearer token clients must send")
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    build_mcp_session(**parts(), token=token, port=port, credentials=CREDENTIALS).run()


if __name__ == "__main__":
    main()
