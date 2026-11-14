"""
A deep agent working in its own git worktree, and a reviewer who reads its work.

``dev`` is a ``DeepAgentConnector``: a LangChain deep agent (``create_deep_agent``)
whose files are its workspace. Its own ``read_file``, ``edit_file`` and ``grep``
work in its worktree, ``ws_commit`` commits there, and everyone else's work is
under ``/peers/<name>/``, read-only. ``reviewer`` is a ``BasicAgentConnector`` that
reads dev's diff with ``ws_diff_of`` and cannot change it.

Ask ``@dev`` for a change, ``@reviewer`` for a review, then ``/ws diff dev`` to
see it yourself and ``/ws merge dev`` to take it — only you can merge.

Run it::

    export OPENAI_API_KEY=sk-...         # any OpenAI-compatible key
    python examples/deep_agent.py [repository]

Without a repository it makes a throwaway one with a small project in it.
``CHATINHO_PROFILE``, ``OPENAI_BASE_URL`` and ``CHATINHO_MODEL`` work as in
``assistant.py``. The model must support tool calling.

Needs ``pip install 'chatinho[all]'`` and ``git``.
"""

import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

from chatinho import BasicAgentConnector, DeepAgentConnector, Endpoint, GitWorktrees, HelpCommand
from chatinho import KeyUnavailable, WorkspaceCommand, build_chat_session

DEV      = "You are a careful developer. Read before you change, keep changes small, and commit each one."
REVIEWER = ("You review the dev's work. Read it with ws_diff_of and ws_read_of (workspace='dev'), and "
            "answer with a short list: bugs, risks, simpler alternatives. You cannot change it.")
WELCOME  = ("'@dev <change>' to have it made; '@reviewer review dev's work' for a review. "
            "'/ws diff dev' shows the work, '/ws merge dev' takes it.")


PROJECT = '''def divide(a, b):
    return a / b
'''


def scratch_repository() -> Path:
    """A throwaway repository holding a small project, for the worktrees to branch from."""
    root = Path(tempfile.mkdtemp(prefix="chatinho-deep-"))
    (root / "calc.py").write_text(PROJECT)
    for args in (["init", "--quiet"], ["add", "-A"], ["commit", "--quiet", "-m", "calc"]):
        subprocess.run(["git", "-c", "user.name=demo", "-c", "user.email=demo@example.invalid", *args],
                       cwd=root, check=True)
    return root


def endpoint() -> Endpoint:
    """The model to use: a profile, else ``OPENAI_*``; exits with a hint when there is no key."""
    try:
        found = Endpoint.load()
        found.check()
    except (KeyUnavailable, ValueError) as exc:
        raise SystemExit("%s; see examples/README.md" % exc)
    return found if found.model else found.with_model("gpt-4o-mini")


def parts(repo: Optional[Path] = None) -> dict:
    """The deep agent, the reviewer, /help and /ws, over one repository's worktrees."""
    model    = endpoint()
    provider = GitWorktrees(repo or scratch_repository())
    return dict(
        connectors = [
            DeepAgentConnector("dev", model, system_prompt=DEV, peers=[]),
            BasicAgentConnector("reviewer", model, system_prompt=REVIEWER, workspace=True, peers=[]),
        ],
        commands   = [HelpCommand(), WorkspaceCommand(provider)],
        backend    = None,
        workspaces = provider,
    )


def main() -> None:
    """Opens the room in the terminal."""
    repo = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    build_chat_session(**parts(repo), title="Deep dev & reviewer", welcome_message=WELCOME, name="me").run()


if __name__ == "__main__":
    main()
