"""
Ask a model about a file on your disk: ``/read notes.md what are the open questions?``.

The assistant from ``assistant.py``, plus a ``/read`` command. The command reads
a local text file, checks it is small UTF-8 text, and addresses the question and
the file's content to the assistant; its answer arrives as a reply in the chat,
and follow-up questions keep the file in its memory.

The file is sent to the endpoint you configured, and nowhere else. Only read
files you are willing to send there.

Run it::

    export OPENAI_API_KEY=sk-...         # any OpenAI-compatible key
    python examples/files.py

``CHATINHO_PROFILE``, ``OPENAI_BASE_URL`` and ``CHATINHO_MODEL`` work as in ``assistant.py``.

Needs ``pip install 'chatinho[all]'``.
"""

import pathlib
import shlex
from typing import Optional

from chatinho import LOCAL, Endpoint, HelpCommand, HookExecute, HookPeers, HookSay, KeyUnavailable
from chatinho import OpenAIConnector
from chatinho import Peers, Reply, ReplyStatus, Say, build_chat_session, name_of, require, tool

SYSTEM   = "You answer questions about the file the user shares, quoting it when useful."
WELCOME  = ("/read <path> [question] sends a local text file (up to 64 KB) and your question to "
            "the assistant — and so to the configured endpoint. Then just keep asking.")
LIMIT    = 64 * 1024
QUESTION = "Summarise this file."


def endpoint() -> Endpoint:
    """The model to use: a profile, else ``OPENAI_*``; exits with a hint when there is no key."""
    try:
        found = Endpoint.load()
        found.check()
    except (KeyUnavailable, ValueError) as exc:
        raise SystemExit("%s; see examples/README.md" % exc)
    return found if found.model else found.with_model("gpt-4o-mini")


def refused(text: str) -> Reply:
    """An error answer from /read; the model is not asked."""
    return Reply("read: %s" % text, status=ReplyStatus.ERROR)


@tool("read", "Ask the assistant about a local text file: /read <path> [question]; quote a path with spaces")
@require(HookExecute)
@require(HookSay)
@require(HookPeers)
class ReadCommand:
    """
    Reads a file and addresses it, with the question, to the assistant.

    It says rather than asks: an addressed say does not wait, so the terminal
    stays free while the model thinks, and the answer comes back as a reply.
    Nothing is returned on success — the assistant's answer is the result.
    """

    say   : Say
    peers : Peers

    async def execute(self, args: str = "", by: int = LOCAL, **kwargs) -> Optional[Reply]:
        del by, kwargs
        try:
            words = shlex.split(args)
        except ValueError:
            return refused("unbalanced quotes in %r" % args)
        if not words:
            return refused("usage: /read <path> [question]")
        where, question = words[0], " ".join(words[1:])
        path = pathlib.Path(where).expanduser()
        if not path.is_file():
            return refused("%s is not a file" % where)
        if path.stat().st_size > LIMIT:
            return refused("%s is larger than 64 KB" % where)
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return refused("%s is not UTF-8 text" % where)
        assistant = next((at for at, who in self.peers().items() if name_of(who) == "assistant"), None)
        if assistant is None:
            return refused("there is no assistant in this chat")
        fence = "````" if "```" in text else "```"
        await self.say("%s\n\nFile: %s\n%s\n%s\n%s" % (
            question or QUESTION, path.name, fence, text, fence), to=assistant)
        return None


def parts() -> dict:
    """The assistant, /read and /help."""
    return dict(
        connectors = [OpenAIConnector("assistant", endpoint(), system=SYSTEM)],
        commands   = [ReadCommand(), HelpCommand()],
        backend    = None,
    )


def main() -> None:
    """Opens the chat in the terminal."""
    build_chat_session(**parts(), title="Files", welcome_message=WELCOME, name="me").run()


if __name__ == "__main__":
    main()
