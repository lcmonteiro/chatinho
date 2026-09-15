"""Tests for the clipboard helper — no terminal, because it needs none.

Textual copies with OSC 52, which a terminal is free to ignore; Termux does.
These cover the second route: a helper program the system already has.
"""

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
