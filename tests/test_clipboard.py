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


# === The /copy command ==========================================================
#
# The third way to copy, and the only one that reports where it is certain to be
# read: as a message in the conversation. A long press may be taken by the
# terminal, a key may not arrive, and a notification may not be visible — but a
# chat that cannot show a message has nothing left to be.

from chatinho import CopyCommand                                    # noqa: E402
from conftest import driven                                         # noqa: E402


async def a_chat_with_copy(monkeypatch, put=lambda text: "xclip"):
    """A started session with /copy in it, and the helper stubbed out."""
    monkeypatch.setattr(chat_clipboard, "put", put)
    return await driven(commands=[CopyCommand()])


async def test_copy_takes_the_last_thing_said(monkeypatch):
    copied = []
    _, view = await a_chat_with_copy(
        monkeypatch, lambda text: copied.append(text) or "termux-clipboard-set")

    await view.say("primeira")
    await view.say("segunda")
    answer = await view.command("copy")

    assert copied == ["segunda"]
    assert "termux-clipboard-set" in answer


async def test_copy_takes_the_message_you_name(monkeypatch):
    copied = []
    _, view = await a_chat_with_copy(monkeypatch, lambda text: copied.append(text) or "xclip")

    first = await view.say("primeira")
    await view.say("segunda")
    answer = await view.command("copy", first)

    assert copied == ["primeira"]
    assert first in answer


async def test_copy_does_not_copy_its_own_invocation(monkeypatch):
    """Everything that crosses the session is in the conversation, /copy included."""
    copied = []
    _, view = await a_chat_with_copy(monkeypatch, lambda text: copied.append(text) or "xclip")

    await view.say("a unica mensagem")
    await view.command("copy")
    await view.command("copy")

    assert copied == ["a unica mensagem", "a unica mensagem"], "never /copy, never its answer"


async def test_copy_says_what_to_install_when_there_is_no_helper(monkeypatch):
    """The failure a phone actually hits, answered where it can be read."""
    _, view = await a_chat_with_copy(monkeypatch, lambda text: None)

    await view.say("alguma coisa")
    answer = await view.command("copy")

    assert "termux-api" in answer and "Termux:API" in answer
    assert "termux-clipboard-set" in answer, "and what it looked for"


async def test_copy_says_so_when_the_id_is_unknown(monkeypatch):
    _, view = await a_chat_with_copy(monkeypatch)

    await view.say("existe")
    answer = await view.command("copy", "msg-999")

    assert "msg-999" in answer and "Nothing to copy" in answer


async def test_copy_says_so_when_there_is_nothing_to_copy(monkeypatch):
    _, view = await a_chat_with_copy(monkeypatch)

    assert "empty" in await view.command("copy")
