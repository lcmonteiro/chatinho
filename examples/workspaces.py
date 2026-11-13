"""
Two agents, each in a git worktree of its own: dev writes and commits, reviewer reads dev's work.

Both are ``BasicAgentConnector`` peers created with ``workspace=True``, so each gets
its workspace as tools: ``ws_read``, ``ws_edit``, ``ws_commit``… on its own, and
``ws_read_of``, ``ws_diff_of``… on anyone else's, which it can only read. Ask
``@dev`` for a change, then ``@reviewer`` to review dev's diff, then look
yourself with ``/ws`` and ``/ws diff dev``, and merge it with ``/ws merge dev``
— only you can.

Run it::

    export OPENAI_API_KEY=sk-...         # any OpenAI-compatible key
    python examples/workspaces.py [repository]

Without a repository it makes a throwaway one with a small project in it. Given
one, the worktrees go under ``<repository>/.chatinho/worktrees`` on branches
``peer/dev`` and ``peer/reviewer``, and nothing else in it is touched until you
merge. ``CHATINHO_PROFILE``, ``OPENAI_BASE_URL`` and ``CHATINHO_MODEL`` work as in
``assistant.py``. The model must support tool calling.

Needs ``pip install 'chatinho[all]'`` and ``git``.
"""

import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

from chatinho import BasicAgentConnector, Endpoint, GitWorktrees, HelpCommand, KeyUnavailable
from chatinho import WorkspaceCommand, build_chat_session

DEV      = ("You are a developer working in your own git worktree. Read before you change, change with "
            "ws_edit or ws_write, and ws_commit when a change is complete. Say what you changed.")
REVIEWER = ("You review the dev's work. Read it with ws_diff_of and ws_read_of (workspace='dev'), and "
            "answer with a short list: bugs, risks, simpler alternatives. You cannot change it.")
WELCOME  = ("'@dev <change>' to have it made; '@reviewer review dev's work' for a review. "
            "/ws lists the workspaces, '/ws diff dev' shows the work, '/ws merge dev' merges it.")

PROJECT = '''def add(a, b):
    return a + b


def divide(a, b):
    return a / b
'''


def endpoint() -> Endpoint:
    """The model to use: a profile, else ``OPENAI_*``; exits with a hint when there is no key."""
    try:
        found = Endpoint.load()
        found.check()
    except (KeyUnavailable, ValueError) as exc:
        raise SystemExit("%s; see examples/README.md" % exc)
    return found if found.model else found.with_model("gpt-4o-mini")


def scratch_repository() -> Path:
    """A throwaway repository holding a small project, for the workspaces to branch from."""
    root = Path(tempfile.mkdtemp(prefix="chatinho-workspaces-"))
    (root / "calc.py").write_text(PROJECT)
    for args in (["init", "--quiet"], ["add", "-A"], ["commit", "--quiet", "-m", "calc"]):
        subprocess.run(["git", "-c", "user.name=demo", "-c", "user.email=demo@example.invalid", *args],
                       cwd=root, check=True)
    return root


def parts(repo: Optional[Path] = None) -> dict:
    """dev and reviewer, each with its workspace as tools, and /help and /ws."""
    model    = endpoint()
    provider = GitWorktrees(repo or scratch_repository())
    return dict(
        connectors = [
            BasicAgentConnector("dev", model, system_prompt=DEV, workspace=True, peers=[]),
            BasicAgentConnector("reviewer", model, system_prompt=REVIEWER, workspace=True, peers=[]),
        ],
        commands   = [HelpCommand(), WorkspaceCommand(provider)],
        backend    = None,
        workspaces = provider,
    )


def main() -> None:
    """Opens the room in the terminal."""
    repo = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    build_chat_session(**parts(repo), title="Dev & reviewer", welcome_message=WELCOME, name="me").run()


if __name__ == "__main__":
    main()
