"""Tests for the clipboard helper — no terminal, because it needs none.

Textual copies with OSC 52, which a terminal is free to ignore; Termux does.
These cover the second route: a helper program the system already has.
"""

import os
import subprocess

import pytest

from chatinho import chat_clipboard


def test_no_helper_installed_is_not_a_failure(monkeypatch):
    """The ordinary case on a plain server: OSC 52 is then the only route."""
    monkeypatch.setattr(chat_clipboard.shutil, "which", lambda name: None)

    assert chat_clipboard.helper() is None
    assert chat_clipboard.put("oi") is None


def test_the_first_helper_on_path_wins(monkeypatch):
    """Termux leads the list: its terminal is the one that drops OSC 52."""
    monkeypatch.setattr(
        chat_clipboard.shutil, "which",
        lambda name: "/usr/bin/%s" % name if name in ("xclip", "termux-clipboard-set") else None,
    )
    assert chat_clipboard.helper() == ["termux-clipboard-set"]

    monkeypatch.setattr(
        chat_clipboard.shutil, "which",
        lambda name: "/usr/bin/%s" % name if name == "xclip" else None,
    )
    assert chat_clipboard.helper() == ["xclip", "-selection", "clipboard"]


def test_the_text_is_fed_to_the_helper_on_stdin(monkeypatch):
    seen = {}

    def fake_run(command, **kwargs):
        seen["command"] = command
        seen["input"] = kwargs.get("input")
        seen["timeout"] = kwargs.get("timeout")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(chat_clipboard.shutil, "which", lambda name: "/usr/bin/" + name)
    monkeypatch.setattr(chat_clipboard.subprocess, "run", fake_run)

    assert chat_clipboard.put("olá") == "termux-clipboard-set"
    assert seen["command"] == ["termux-clipboard-set"]
    assert seen["input"] == "olá".encode("utf-8")
    assert seen["timeout"] == chat_clipboard.TIMEOUT


@pytest.mark.parametrize("blow_up", [
    OSError("no such thing"),
    subprocess.TimeoutExpired("termux-clipboard-set", 5),
    subprocess.CalledProcessError(1, "termux-clipboard-set"),
])
def test_a_helper_that_fails_is_logged_and_not_raised(monkeypatch, blow_up):
    """The chat has already copied by the other route; a clipboard is not
    worth interrupting a conversation for."""
    def fake_run(command, **kwargs):
        raise blow_up

    monkeypatch.setattr(chat_clipboard.shutil, "which", lambda name: "/usr/bin/" + name)
    monkeypatch.setattr(chat_clipboard.subprocess, "run", fake_run)

    assert chat_clipboard.put("oi") is None


# === The real subprocess, not a stand-in ========================================
#
# The tests above replace `chat_clipboard.put`, which proves the callers do the
# right thing and proves nothing about the thing itself. These run a helper that
# is really on PATH and really executed, because the wiring from copy_message
# through a worker, an executor and subprocess.run is exactly where a copy can
# be wired up wrongly and still pass a suite full of doubles.


@pytest.fixture
def a_helper_on_path(tmp_path, monkeypatch):
    """Puts a working `termux-clipboard-set` on PATH, writing to a file."""
    written = tmp_path / "clipboard.txt"
    helper  = tmp_path / "termux-clipboard-set"
    helper.write_text("#!/usr/bin/env bash\ncat > %s\n" % written)
    helper.chmod(0o755)
    monkeypatch.setenv("PATH", "%s:%s" % (tmp_path, os.environ["PATH"]))
    return written


def test_put_really_runs_the_helper(a_helper_on_path):
    assert chat_clipboard.put("texto a sério") == "termux-clipboard-set"
    assert a_helper_on_path.read_text() == "texto a sério"


async def test_the_app_really_reaches_the_clipboard(a_helper_on_path):
    """End to end with nothing stubbed: the log's copy, and the clipboard.

    `ChatLog.copy_message` hands the text to a worker, which hands it to an
    executor, which runs a subprocess. Every other test of that path replaces
    the last step, so this one lets all four happen.
    """
    from chatinho import ChatSession
    from chatinho.chat_app import ChatApp

    app     = ChatApp()
    session = ChatSession()
    session.add_connector(app)
    await session.start()

    async with app.run_test(size=(80, 24)) as pilot:
        await app.say("o que vai para o clipboard")
        await pilot.pause()

        app._chat_log.copy_message(app.messages[0].id)
        for _ in range(30):
            await pilot.pause()
            if a_helper_on_path.exists():
                break

    await session.close()
    assert a_helper_on_path.read_text() == "o que vai para o clipboard"
