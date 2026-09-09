"""Tests for the Textual presentation.

The app is built with ``create_chat`` and mounted via ``App.run_test()``, so
the widgets are available to the code under test. The presentation is a
peer like any other — registered at LOCAL — so these tests are the same
model as the headless ones, with a terminal attached.
"""

import asyncio
import threading

import pytest
from textual.binding import NoBinding
from textual.widgets import Input

from chatinho import (
    LOCAL,
    TOOL,
    Ask,
    HelpCommand,
    HookAsk,
    HookExecute,
    connector,
    create_chat,
    require,
    tool,
)


@tool("eco", "repete")
@require(HookExecute)
class _Eco:
    """A command that answers; the session is what puts the answer in the log.

    It does not also say it: what it answers is posted in TOOL's name, so
    saying it too would put the same line in the conversation twice.
    """

    async def execute(self, args="", by=LOCAL, **kwargs) -> str:
        return "eco: %s" % args


@tool("mudo", "answers without writing")
@require(HookExecute)
class _Mudo:
    """A command that only answers: nothing of it reaches the conversation."""

    async def execute(self, args="", by=LOCAL, **kwargs) -> str:
        return "só para quem correu"


@connector("agente")
@require(HookAsk)
class _Agente:
    ask : Ask


# === Saying =====================================================================


async def test_say_returns_an_id_and_stores():
    app = create_chat()
    async with app.run_test():
        assert await app.say("hello") == "msg-1"
        msg = app.messages[0]
        assert (msg.text, msg.frm, msg.to) == ("hello", LOCAL, None)
        assert msg.is_local is True


async def test_the_welcome_message_is_the_app_saying_it():
    app = create_chat(welcome_message="Bem-vindo")
    async with app.run_test():
        assert [m.text for m in app.messages] == ["Bem-vindo"]


async def test_submitting_text_says_it():
    app = create_chat()
    async with app.run_test() as pilot:
        inp = app.query_one("#input-line", Input)
        inp.value = "  ola  "
        await pilot.press("enter")
        await pilot.pause()
        assert [m.text for m in app.messages] == ["ola"]
        assert app.query_one("#input-line", Input).value == ""


async def test_blank_input_says_nothing():
    app = create_chat()
    async with app.run_test() as pilot:
        app.query_one("#input-line", Input).value = "   "
        await pilot.press("enter")
        await pilot.pause()
    assert app.messages == []


# === Commands are run, and the running is recorded ==============================


async def test_running_a_command_is_recorded_whole():
    """The invocation and the answer are both messages, in that order."""
    app = create_chat(commands=[_Eco(), _Mudo()])
    async with app.run_test() as pilot:
        assert await app.command("eco", "ola") == "eco: ola"
        assert await app.command("mudo") == "só para quem correu"
        await pilot.pause()
        assert [m.text for m in app.messages] == [
            "/eco ola", "eco: ola", "/mudo", "só para quem correu",
        ]


async def test_what_a_command_writes_is_not_the_user_speaking():
    """A connector answering the user must not answer /help's output.

    Two things keep that true now that both cross the session: what the command
    answered comes from TOOL, and the invocation is addressed to TOOL rather
    than said to the room, so a peer that replies to broadcasts sees neither as
    the user speaking.
    """
    app = create_chat(commands=[_Eco()])
    async with app.run_test() as pilot:
        await app.command("eco", "ola")
        await pilot.pause()
        invocacao, resposta = app.messages
        assert invocacao.to == TOOL and invocacao.is_broadcast is False
        assert resposta.frm == TOOL and resposta.is_local is False


async def test_submitting_a_slash_runs_the_tool():
    app = create_chat(commands=[_Eco()])
    async with app.run_test() as pilot:
        inp = app.query_one("#input-line", Input)
        inp.value = "/eco bom dia"
        await pilot.press("enter")
        await pilot.pause()
        assert [m.text for m in app.messages] == ["/eco bom dia", "eco: bom dia"]


async def test_an_unknown_command_says_so():
    app = create_chat()
    async with app.run_test() as pilot:
        assert await app.command("nope") is None
        await pilot.pause()
    assert app.messages[-1].text == "Unknown command: /nope"


async def test_help_lists_the_tools_that_can_be_asked():
    app = create_chat(commands=[HelpCommand(), _Eco()])
    async with app.run_test() as pilot:
        answer = await app.command("help")
        await pilot.pause()
    assert "/help" in answer and "/eco" in answer


# === Being asked ================================================================


async def test_a_connector_can_ask_the_user_and_the_reply_answers_it():
    """The whole round trip, with no routing code in the presentation."""
    agente = _Agente()
    app = create_chat(connectors=[agente])
    async with app.run_test() as pilot:
        question = asyncio.create_task(agente.ask(LOCAL, "Autorizas?"))
        await pilot.pause()
        asked = app.messages[-1]
        assert (asked.frm, asked.to, asked.text) == (1, LOCAL, "Autorizas?")

        await app.say("sim", reply_to=asked.id)
        assert await question == "sim"
        await pilot.pause()
    assert [m.text for m in app.messages] == ["Autorizas?", "sim"]


# === Threading ==================================================================


async def test_a_message_from_another_thread_reaches_the_log():
    """A connector with its own server thread must be able to speak."""
    app = create_chat()
    async with app.run_test() as pilot:
        loop = asyncio.get_running_loop()
        done = threading.Event()

        def from_thread() -> None:
            asyncio.run_coroutine_threadsafe(app.say("de outra thread"), loop).result(5)
            done.set()

        threading.Thread(target=from_thread, daemon=True).start()
        while not done.is_set():
            await pilot.pause()
        await pilot.pause()
    assert [m.text for m in app.messages] == ["de outra thread"]


# === Rendering ==================================================================


async def test_a_commands_answer_is_rendered_as_a_reply_to_it():
    """What a command answered quotes the invocation, and is headed Tool.

    The invocation and the answer are both messages now, and the answer carries
    ``reply_to``, so the log renders it the way it renders any reply.
    """
    app = create_chat(commands=[_Eco()])
    async with app.run_test() as pilot:
        await app.command("eco", "ola")
        await pilot.pause()
        log = app.query_one("#chat-log")
        cabecalhos = [str(w.visual) for w in log.query(".message-header")]
        citacoes   = [str(w.visual) for w in log.query(".message-quote")]
        assert "You" in cabecalhos[0] and "↳ replying" not in cabecalhos[0]
        assert "Tool" in cabecalhos[1] and "↳ replying" in cabecalhos[1]
        assert citacoes == ["↳ %s: /eco ola…" % app.messages[0].id]


async def test_the_log_renders_what_the_history_holds():
    app = create_chat(commands=[_Eco()])
    async with app.run_test() as pilot:
        await app.say("uma")
        await app.command("eco", "duas")
        await pilot.pause()
        log = app.query_one("#chat-log")
        # Three: what the user said, the invocation, and what it answered.
        assert len(log._msg_widgets) == len(app.messages) == 3


async def test_only_the_window_is_rendered():
    app = create_chat(max_displayed=3)
    async with app.run_test() as pilot:
        for n in range(6):
            await app.say("m%d" % n)
        await pilot.pause()
        assert len(app.messages) == 6
        assert app._rendered_msg_ids == [m.id for m in app.messages[-3:]]


# === Threading a reply ==========================================================


async def test_get_replies_reads_the_thread_back():
    app = create_chat()
    async with app.run_test():
        first = await app.say("original")
        reply = await app.say("resposta", reply_to=first)
        assert app.get_replies(first) == [reply]
        assert app.get_replies("msg-999") == []


async def test_send_pending_reply_uses_the_clicked_target():
    app = create_chat()
    async with app.run_test() as pilot:
        target = await app.say("alvo")
        await pilot.pause()
        app._set_reply_target(target)
        reply = await app.send_pending_reply("resposta")
        assert app._find_message(reply).reply_to == target
        assert app._reply_target is None


async def test_send_pending_reply_does_nothing_without_a_target():
    app = create_chat()
    async with app.run_test():
        assert await app.send_pending_reply("resposta") is None
        assert app.messages == []


# === The quit key ===============================================================


def _actions_for(app, key):
    """The actions bound to *key*, or None when nothing is."""
    try:
        return [binding.action for binding in app._bindings.get_bindings_for_key(key)]
    except NoBinding:
        return None


def test_the_quit_key_defaults_to_textuals_own():
    app = create_chat()
    assert _actions_for(app, "ctrl+q") == ["quit"]


def test_a_given_quit_key_replaces_the_default_rather_than_joining_it():
    """_Chat declares no BINDINGS: quit is inherited, and Textual *merges*.

    Declaring a new binding in the subclass would leave ctrl+q quitting as
    well, which is the bug this guards. The instance's own map is what moves.
    """
    app = create_chat(quit_key="ctrl+g")
    assert _actions_for(app, "ctrl+g") == ["quit"]
    assert _actions_for(app, "ctrl+q") is None


async def test_the_quit_key_actually_quits_and_the_old_one_does_not():
    """The map saying so is not the same as the app doing so."""
    app = create_chat(quit_key="ctrl+g")
    async with app.run_test() as pilot:
        await pilot.press("ctrl+q")
        await pilot.pause()
        assert app.is_running, "ctrl+q should no longer quit"

        await pilot.press("ctrl+g")
        await pilot.pause()
        assert not app.is_running


def test_rebinding_quit_leaves_the_other_bindings_alone():
    """ctrl+c is help_quit and ctrl+p is the command palette; neither moves."""
    default = create_chat()
    rebound = create_chat(quit_key="f10")
    for key in ("ctrl+c", "ctrl+p"):
        assert _actions_for(rebound, key) == _actions_for(default, key)


@pytest.mark.parametrize("bad", ["", "   ", "not a key", "ctrl+", "hyperx+q"])
def test_a_quit_key_textual_could_never_receive_is_refused(bad):
    """Binding() accepts 'not a key' and then never fires — a silent no-op."""
    with pytest.raises(ValueError, match="quit_key"):
        create_chat(quit_key=bad)


def test_a_single_character_and_a_named_key_are_both_accepted():
    assert _actions_for(create_chat(quit_key="q"), "q") == ["quit"]
    assert _actions_for(create_chat(quit_key="escape"), "escape") == ["quit"]
