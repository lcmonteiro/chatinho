"""Tests for the Textual presentation.

The app is built with ``create_chat`` and mounted via ``App.run_test()``, so
the widgets are available to the code under test. The presentation is a
peer like any other — registered at LOCAL — so these tests are the same
model as the headless ones, with a terminal attached.
"""

import asyncio
import threading

from textual.widgets import Input

from chatinho import (
    LOCAL,
    TOOL,
    Ask,
    HelpCommand,
    HookAsk,
    HookExecute,
    HookSay,
    Say,
    connector,
    create_chat,
    require,
    tool,
)


@tool("eco", "repete")
@require(HookExecute)
@require(HookSay)
class _Eco:
    """A command that writes what it produces, so the user sees it."""

    say : Say

    async def execute(self, args="", by=LOCAL, **kwargs) -> str:
        await self.say("eco: %s" % args)
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


# === Commands are asks ==========================================================


async def test_a_command_is_seen_only_if_it_writes():
    """The invocation is not a message, and neither is the answer."""
    app = create_chat(commands=[_Eco(), _Mudo()])
    async with app.run_test() as pilot:
        assert await app.command("eco", "ola") == "eco: ola"
        assert await app.command("mudo") == "só para quem correu"
        await pilot.pause()
        assert [m.text for m in app.messages] == ["eco: ola"]


async def test_what_a_command_writes_is_not_the_user_speaking():
    """A connector answering the user must not answer /help's output."""
    app = create_chat(commands=[_Eco()])
    async with app.run_test() as pilot:
        await app.command("eco", "ola")
        await pilot.pause()
        assert app.messages[0].frm == TOOL
        assert app.messages[0].is_local is False


async def test_submitting_a_slash_runs_the_tool():
    app = create_chat(commands=[_Eco()])
    async with app.run_test() as pilot:
        inp = app.query_one("#input-line", Input)
        inp.value = "/eco bom dia"
        await pilot.press("enter")
        await pilot.pause()
        assert [m.text for m in app.messages] == ["eco: bom dia"]


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


async def test_the_log_renders_what_the_history_holds():
    app = create_chat(commands=[_Eco()])
    async with app.run_test() as pilot:
        await app.say("uma")
        await app.command("eco", "duas")
        await pilot.pause()
        log = app.query_one("#chat-log")
        # Two: what the user said, and what the command wrote. The invocation
        # and the answer are neither.
        assert len(log._msg_widgets) == len(app.messages) == 2


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
