"""Tests for the Textual presentation.

The app is built with ``build_chat`` and mounted via ``App.run_test()``, so
the widgets are available to the code under test. The presentation is a
peer like any other — registered at LOCAL — so these tests are the same
model as the headless ones, with a terminal attached.
"""

import asyncio
import inspect
import threading
from dataclasses import replace

import pytest
from textual import events
from textual.binding import NoBinding
from textual.color import Color

from chatinho.chat_app import ChatApp
from chatinho.chat_input import NEWLINE_KEYS, CommandInput
from chatinho.chat_log import preview_of
from chatinho import (
    LOCAL,
    build_chat,
    TOOL,
    Ask,
    HelpCommand,
    HookAnswer,
    HookAsk,
    HookExecute,
    connector,
    ChatSession,
    ChatStyle,
    require,
    tool,
)


async def chat_app(connectors=None, commands=None, backend=None, **kwargs):
    """The terminal peer, built and attached the way build_chat does it.

    ``build_chat`` returns the *session* — the terminal is one of its
    peers, not its owner — so a test that drives the app builds it the same way
    a caller would: an ordinary connector, attached to an ordinary session. It
    does not hold the session either, so this starts it directly rather than
    relying on the app to reach back for it.
    """
    session = ChatSession(connectors=connectors, commands=commands, backend=backend)
    app = ChatApp(**kwargs)
    session.add_connector(app)
    await session.start()
    return app


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
    app = await chat_app()
    async with app.run_test():
        assert await app.say("hello") == "msg-1"
        msg = app.messages[0]
        assert (msg.text, msg.frm, msg.to) == ("hello", LOCAL, None)
        assert msg.is_local is True


async def test_the_welcome_message_is_the_app_saying_it():
    app = await chat_app(welcome_message="Bem-vindo")
    async with app.run_test():
        assert [m.text for m in app.messages] == ["Bem-vindo"]


async def test_submitting_text_says_it():
    app = await chat_app()
    async with app.run_test() as pilot:
        inp = app.query_one("#input-line", CommandInput)
        inp.text = "  ola  "
        await pilot.press("enter")
        await pilot.pause()
        assert [m.text for m in app.messages] == ["ola"]
        assert app.query_one("#input-line", CommandInput).text == ""


async def test_blank_input_says_nothing():
    app = await chat_app()
    async with app.run_test() as pilot:
        app.query_one("#input-line", CommandInput).text = "   "
        await pilot.press("enter")
        await pilot.pause()
    assert app.messages == []


# === Commands are run, and the running is recorded ==============================


async def test_running_a_command_is_recorded_whole():
    """The invocation and the answer are both messages, in that order."""
    app = await chat_app(commands=[_Eco(), _Mudo()])
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
    app = await chat_app(commands=[_Eco()])
    async with app.run_test() as pilot:
        await app.command("eco", "ola")
        await pilot.pause()
        invocacao, resposta = app.messages
        assert invocacao.to == TOOL and invocacao.is_broadcast is False
        assert resposta.frm == TOOL and resposta.is_local is False


async def test_submitting_a_slash_runs_the_tool():
    app = await chat_app(commands=[_Eco()])
    async with app.run_test() as pilot:
        inp = app.query_one("#input-line", CommandInput)
        inp.text = "/eco bom dia"
        await pilot.press("enter")
        await pilot.pause()
        assert [m.text for m in app.messages] == ["/eco bom dia", "eco: bom dia"]


async def test_an_unknown_command_says_so():
    app = await chat_app()
    async with app.run_test() as pilot:
        assert await app.command("nope") is None
        await pilot.pause()
    assert app.messages[-1].text == "Unknown command: /nope"


async def test_help_lists_the_tools_that_can_be_asked():
    app = await chat_app(commands=[HelpCommand(), _Eco()])
    async with app.run_test() as pilot:
        answer = await app.command("help")
        await pilot.pause()
    assert "/help" in answer and "/eco" in answer


# === Being asked ================================================================


async def test_a_connector_can_ask_the_user_and_the_reply_answers_it():
    """The whole round trip, with no routing code in the presentation."""
    agente = _Agente()
    app = await chat_app(connectors=[agente])
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
    app = await chat_app()
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
    """What a command answered quotes the invocation, and is headed @tool.

    The invocation and the answer are both messages now, and the answer carries
    ``reply_to``, so the log renders it the way it renders any reply.
    """
    app = await chat_app(commands=[_Eco()])
    async with app.run_test() as pilot:
        await app.command("eco", "ola")
        await pilot.pause()
        log = app.query_one("#chat-log")
        cabecalhos = [str(w.visual) for w in log.query(".message-header")]
        citacoes   = [str(w.visual) for w in log.query(".message-quote")]
        assert "@chat" in cabecalhos[0] and "↳ replying" not in cabecalhos[0]
        assert "@tool" in cabecalhos[1] and "↳ replying" in cabecalhos[1]
        assert citacoes == ["↳ %s: /eco ola…" % app.messages[0].id]


async def test_the_log_renders_what_the_history_holds():
    app = await chat_app(commands=[_Eco()])
    async with app.run_test() as pilot:
        await app.say("uma")
        await app.command("eco", "duas")
        await pilot.pause()
        log = app.query_one("#chat-log")
        # Three: what the user said, the invocation, and what it answered.
        assert len(log._msg_widgets) == len(app.messages) == 3


async def test_only_the_window_is_rendered():
    app = await chat_app(max_displayed=3)
    async with app.run_test() as pilot:
        for n in range(6):
            await app.say("m%d" % n)
        await pilot.pause()
        assert len(app.messages) == 6
        assert app._rendered_msg_ids == [m.id for m in app.messages[-3:]]


# === Threading a reply ==========================================================


async def test_get_replies_reads_the_thread_back():
    app = await chat_app()
    async with app.run_test():
        first = await app.say("original")
        reply = await app.say("resposta", reply_to=first)
        assert app.get_replies(first) == [reply]
        assert app.get_replies("msg-999") == []


async def test_send_pending_reply_uses_the_clicked_target():
    app = await chat_app()
    async with app.run_test() as pilot:
        target = await app.say("alvo")
        await pilot.pause()
        app._set_reply_target(target)
        reply = await app.send_pending_reply("resposta")
        assert app._find_message(reply).reply_to == target
        assert app._reply_target is None


async def test_send_pending_reply_does_nothing_without_a_target():
    app = await chat_app()
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


async def test_the_quit_key_defaults_to_textuals_own():
    app = await chat_app()
    assert _actions_for(app, "ctrl+q") == ["quit"]


async def test_a_given_quit_key_replaces_the_default_rather_than_joining_it():
    """ChatApp declares no BINDINGS: quit is inherited, and Textual *merges*.

    Declaring a new binding in the subclass would leave ctrl+q quitting as
    well, which is the bug this guards. The instance's own map is what moves.
    """
    app = await chat_app(quit_key="ctrl+g")
    assert _actions_for(app, "ctrl+g") == ["quit"]
    assert _actions_for(app, "ctrl+q") is None


async def test_the_quit_key_actually_quits_and_the_old_one_does_not():
    """The map saying so is not the same as the app doing so."""
    app = await chat_app(quit_key="ctrl+g")
    async with app.run_test() as pilot:
        await pilot.press("ctrl+q")
        await pilot.pause()
        assert app.is_running, "ctrl+q should no longer quit"

        await pilot.press("ctrl+g")
        await pilot.pause()
        assert not app.is_running


async def test_rebinding_quit_leaves_the_other_bindings_alone():
    """ctrl+c is help_quit and ctrl+p is the command palette; neither moves."""
    default = await chat_app()
    rebound = await chat_app(quit_key="f10")
    for key in ("ctrl+c", "ctrl+p"):
        assert _actions_for(rebound, key) == _actions_for(default, key)


@pytest.mark.parametrize("bad", ["", "   ", "not a key", "ctrl+", "hyperx+q"])
async def test_a_quit_key_textual_could_never_receive_is_refused(bad):
    """Binding() accepts 'not a key' and then never fires — a silent no-op."""
    with pytest.raises(ValueError, match="quit_key"):
        await chat_app(quit_key=bad)


async def test_a_single_character_and_a_named_key_are_both_accepted():
    assert _actions_for(await chat_app(quit_key="q"), "q") == ["quit"]
    assert _actions_for(await chat_app(quit_key="escape"), "escape") == ["quit"]


def test_build_chat_returns_the_session_with_the_terminal_attached():
    """The session owns the loop; the terminal is one of the peers it serves."""
    session = build_chat(commands=[_Eco()])

    assert isinstance(session, ChatSession)
    assert session.id_of("chat") == LOCAL, "the terminal is the session's frontend"
    assert callable(getattr(session, "run", None))


async def test_the_terminal_serves_until_the_user_quits():
    """serve() is what ChatSession.run() runs, and it is run_async underneath.

    ``run()`` would try to start a second event loop inside the session's own.
    """
    app = await chat_app(quit_key="ctrl+g")
    serving = asyncio.create_task(app.run_async(headless=True))
    await asyncio.sleep(0.2)
    assert not serving.done(), "still serving while the app is up"

    app.exit()
    await asyncio.wait_for(serving, timeout=5)


# === How a bubble is drawn ======================================================
#
# A bubble is an outline, not a fill: the border carries the colour and the chat
# background shows through. The one background in the log is the message the
# user has selected to reply to.


@connector("outro")
@require(HookAnswer)
class _Outro:
    """Someone other than the user, so a received bubble exists to measure."""

    async def answer(self, msg) -> str:
        return "recebida"


def _bubbles(app):
    """The bubble widgets currently in the log, oldest first."""
    return list(app.query(".message-bubble"))


async def test_a_bubble_is_as_wide_as_its_widest_line():
    """Dynamic, not 90% of the window — and never past the maximum."""
    app = await chat_app()
    async with app.run_test(size=(100, 30)) as pilot:
        await app.say("oi")
        await app.say("palavra " * 40)
        await pilot.pause()

        short, long = _bubbles(app)
        assert short.outer_size.width < 40, "a short message takes a short bubble"
        assert long.outer_size.width == 72, "a long one stops at bubble_max_width"


async def test_a_bubble_has_no_background_until_it_is_the_reply_target():
    """The fill is what selection means; nothing else in the log has one."""
    app = await chat_app()
    async with app.run_test() as pilot:
        await app.say("oi")
        await pilot.pause()

        bubble = _bubbles(app)[0]
        assert bubble.styles.background.a == 0, "drawn as an outline only"

        app._chat_log.set_reply_target(app.messages[0].id)
        await pilot.pause()
        assert bubble.styles.background.a > 0, "selected: now it is filled"

        app._chat_log.clear_reply_target()
        await pilot.pause()
        assert bubble.styles.background.a == 0, "deselected: back to an outline"


async def test_who_spoke_is_on_the_container_whichever_side_it_takes():
    """The side is a style; the class is what the log routes on.

    Alignment itself is asserted where ``local_align`` is — both defaults and
    the other side, in one place. What matters here is that every message
    carries one of the two classes the stylesheet aligns by.
    """
    app = await chat_app(connectors=[_Outro()])
    async with app.run_test(size=(100, 30)) as pilot:
        outro = next(at for at, who in app.peers().items()
                     if getattr(who, "name", None) == "outro")
        await app.say("eu")
        await app.ask(outro, "e tu?")
        await pilot.pause()

        kinds = [{"sent", "received"} & w.classes for w in app.query(".message-container")]
        assert all(len(k) == 1 for k in kinds), "exactly one of the two, never both"
        assert {"sent"} in kinds and {"received"} in kinds, "both kinds are in the log"


# === The input takes more than one line =========================================


@pytest.mark.parametrize("newline_key", NEWLINE_KEYS)
async def test_a_newline_key_opens_a_line_and_enter_sends_both(newline_key):
    """Input is single-line by construction; this is why it became a TextArea.

    Parametrized over the constant rather than over a list written out here, so
    a key added to it cannot arrive untested.
    """
    app = await chat_app()
    async with app.run_test() as pilot:
        await pilot.press("a")
        await pilot.press(newline_key)
        await pilot.press("b")
        assert app.query_one("#input-line", CommandInput).text == "a\nb"

        await pilot.press("enter")
        await pilot.pause()
        assert [m.text for m in app.messages] == ["a\nb"]
        assert app.query_one("#input-line", CommandInput).text == ""


async def test_a_space_before_enter_opens_a_line_and_is_consumed():
    """The default escape, and the way in that needs no key at all.

    Ending a line with a space and carrying on is what continuing already
    feels like, so the gesture is the intention rather than a code for it.
    """
    app = await chat_app()
    async with app.run_test() as pilot:
        await pilot.press("a", "space", "enter", "b")
        assert app.query_one("#input-line", CommandInput).text == "a\nb"
        assert app.messages == [], "the space opened a line, it did not send"

        await pilot.press("enter")
        await pilot.pause()
        assert [m.text for m in app.messages] == ["a\nb"]


async def test_a_message_that_really_ends_in_the_escape_can_still_be_sent():
    """Which is why the check is anchored to the cursor, not to the text.

    Move off the end and Enter means what it usually means. There is no other
    escape, so without this the character would be unsendable at the end of a
    message — and `submit` strips the text anyway, so with a space the whole
    question is invisible.
    """
    app = await chat_app()
    async with app.run_test() as pilot:
        await pilot.press("a", "space", "left", "enter")
        await pilot.pause()
        assert [m.text for m in app.messages] == ["a"], "stripped on the way out"


async def test_the_escape_is_configurable_and_can_be_turned_off():
    """A space suits a chat; a backslash suits somebody who types prose in one."""
    app = await chat_app(newline_escape="\\")
    async with app.run_test() as pilot:
        await pilot.press("a", "space", "enter")
        await pilot.pause()
        assert [m.text for m in app.messages] == ["a"], "a space is no longer the escape"

        await pilot.press("b", "backslash", "enter", "c")
        assert app.query_one("#input-line", CommandInput).text == "b\nc"

    off = await chat_app(newline_escape=None)
    async with off.run_test() as pilot:
        await pilot.press("a", "space", "enter")
        await pilot.pause()
        assert [m.text for m in off.messages] == ["a"], "no escape at all"


@pytest.mark.parametrize("bad", ["", "  ", "\n", 7])
def test_an_escape_that_could_never_fire_is_refused(bad):
    """`\n` is the silent one: the escape is looked for on the cursor's own
    line, which never holds a newline, so it would simply never match."""
    with pytest.raises(ValueError, match="newline_escape"):
        CommandInput(newline_escape=bad)


#: What a terminal really puts on the wire for each newline key, and what
#: Textual makes of it. `CSI 13 ; n u` — 13 is Return, n-1 the modifier
#: bitmask — arrives only from a terminal that answers Textual's request for
#: the enhanced keyboard protocol; `LF` needs no protocol, being a byte of its
#: own since teletypes rather than a modified Return.
_ON_THE_WIRE = {
    "ctrl+j"      : "\n",             # LF 0x0A
    "ctrl+enter"  : "\x1b[13;5u",
    "shift+enter" : "\x1b[13;2u",
    "alt+enter"   : "\x1b[13;3u",
}

#: What the same keys degrade to where that protocol is not spoken, which is
#: the case this whole constant exists for. Termux is such a terminal.
#: `shift+enter` is not listed because it degrades exactly as `ctrl+enter`
#: does — a bare carriage return — and a second row would prove it twice.
_WITHOUT_THE_PROTOCOL = {
    "ctrl+j"     : ("\n",       ["ctrl+j"]),   # unchanged: it was never modified
    "ctrl+enter" : ("\r",       ["enter"]),    # Enter's own byte, so it SENDS
    "alt+enter"  : ("\x1b\r",   []),           # no key comes out at all
}


def test_at_least_one_newline_key_arrives_without_the_enhanced_protocol():
    """What a key is *called* is ours; whether it arrives is the terminal's.

    `pilot.press` synthesises the name directly, so every test above proves the
    handling and nothing at all about the wire. This one feeds Textual's own
    parser the bytes, and guards the invariant a bug report is actually about:
    **something has to work on a terminal that answers no protocol**, or the
    input has no second line at all. Shipping `ctrl+enter` alone failed exactly
    there, on a phone.

    The degradations are named one by one because each is reported as a
    different bug — "ctrl+enter sends the message" and "alt+enter does
    nothing". What the parser does with whatever *follows* an `ESC CR` is the
    driver's timing, which this does not model and so does not claim.
    """
    from textual._xterm_parser import XTermParser

    assert set(_ON_THE_WIRE) == set(NEWLINE_KEYS), \
        "a newline key was added or removed without its bytes"
    for name, sequence in _ON_THE_WIRE.items():
        assert [e.key for e in XTermParser().feed(sequence)] == [name]

    survivors = [name for name, (seq, keys) in _WITHOUT_THE_PROTOCOL.items() if keys == [name]]
    assert survivors, "every newline key would then need a protocol to arrive"
    for name, (sequence, expected) in _WITHOUT_THE_PROTOCOL.items():
        assert [e.key for e in XTermParser().feed(sequence)] == expected, name


async def test_the_input_grows_with_the_lines_up_to_its_maximum():
    """It starts one row tall and stops at input_max_height, borders included."""
    app = await chat_app()
    async with app.run_test(size=(100, 30)) as pilot:
        inp = app.query_one("#input-line", CommandInput)
        assert inp.outer_size.height == 3, "one row of text, plus its border"

        inp.insert("um\ndois\ntres")
        await pilot.pause()
        assert inp.outer_size.height == 5, "grew with the lines"

        inp.insert("\nx" * 20)
        await pilot.pause()
        assert inp.outer_size.height == 8, "and stops at the maximum"


async def test_up_moves_the_cursor_when_no_suggestion_is_open():
    """Up and Down belong to the popup only while it has something to move."""
    app = await chat_app(commands=[_Eco()])
    async with app.run_test() as pilot:
        inp = app.query_one("#input-line", CommandInput)
        inp.insert("um\ndois")
        inp.focus()
        await pilot.pause()
        assert inp.cursor_location == (1, 4)

        await pilot.press("up")
        await pilot.pause()
        assert inp.cursor_location[0] == 0, "moved a line up, not through a popup"


# === Who spoke, in colour ========================================================


@connector("segundo")
@require(HookAnswer)
class _Segundo:
    async def answer(self, msg) -> str:
        return "sou o segundo"


async def test_each_peer_gets_its_own_header_colour():
    """The header carries who spoke and the message id, so it is what is tinted."""
    app = await chat_app(connectors=[_Outro(), _Segundo()])
    async with app.run_test(size=(100, 30)) as pilot:
        at = {getattr(who, "name", None): i for i, who in app.peers().items()}
        await app.say("eu")
        await app.ask(at["outro"], "e tu?")
        await app.ask(at["segundo"], "e tu?")
        await pilot.pause()

        colours = {}
        for msg in app.messages:
            container = app._chat_log._msg_widgets.get(msg.id)
            if container is not None:
                colours[msg.frm] = str(container.query_one(".message-header").styles.color)

        assert len(colours) >= 3, "the user and both connectors are in the log"
        assert len(set(colours.values())) == len(colours), "no two peers share a colour"


def test_a_command_is_not_given_a_peer_slot():
    """TOOL has no id of its own, so it gets a name rather than a number."""
    style = ChatStyle()
    assert style.header_class(TOOL) == "peer-tool"
    assert style.header_class(LOCAL) == "peer-0"


def test_the_palette_wraps_round_rather_than_running_out():
    """More peers than colours is ordinary; running out of them would not be."""
    style = ChatStyle()
    width = len(style.peer_headers)
    assert style.header_class(width) == style.header_class(0)
    assert style.header_class(width + 1) == style.header_class(1)


def test_a_palette_with_no_colours_is_refused():
    with pytest.raises(ValueError, match="peer_headers"):
        ChatStyle(peer_headers=())


async def test_the_scrollbar_wears_the_palette_too():
    """Textual styles a scrollbar with properties, not with a class of its own.

    The four ``scrollbar_*`` fields used to be rendered into a ``.scrollbar``
    rule, which is a valid selector matching nothing — so the fields were set,
    the stylesheet parsed, and the default theme's blue still ran down the side
    of the chat. Only a render showed it.
    """
    app = await chat_app()
    async with app.run_test(size=(60, 14)) as pilot:
        for i in range(6):
            await app.say("mensagem %d, comprida o suficiente para encher a linha toda" % i)
        await pilot.pause()

        log   = app._chat_log
        style = ChatStyle()
        assert log.show_vertical_scrollbar, "narrow and full: the bar is up to be looked at"
        assert log.styles.scrollbar_background       == Color.parse(style.scrollbar_bg)
        assert log.styles.scrollbar_color            == Color.parse(style.scrollbar_color)
        assert log.styles.scrollbar_background_hover == Color.parse(style.scrollbar_hover_bg)
        assert log.styles.scrollbar_color_hover      == Color.parse(style.scrollbar_hover_color)


# === A bubble stays inside the window ============================================


async def test_the_scrollbar_is_one_cell_wide():
    """Textual's own is two, which is a lot to give up beside a narrow chat.

    ``scrollbar_size_vertical`` is what the widget actually reserves, so this
    fails on the default rather than merely on a field being unset — the
    `.scrollbar` rule that matched nothing once made exactly that mistake.
    """
    app = await chat_app()
    async with app.run_test(size=(60, 24)) as pilot:
        for i in range(30):
            await app.say("mensagem %d" % i)
        await pilot.pause()

        log = app._chat_log
        assert log.show_vertical_scrollbar, "narrow and full: the bar is up to be looked at"
        assert log.scrollbar_size_vertical == 1, "one cell, not Textual's two"


async def test_the_scrollbar_width_is_a_style_field():
    """And a wider one is still reachable, for a terminal where one is too thin."""
    app = await chat_app(style=replace(ChatStyle(), scrollbar_size=3))
    async with app.run_test(size=(60, 24)) as pilot:
        for i in range(30):
            await app.say("mensagem %d" % i)
        await pilot.pause()

        assert app._chat_log.scrollbar_size_vertical == 3


def test_a_scrollbar_with_no_width_is_refused_at_construction():
    """Textual refuses it too, but at mount, pointing at the generated CSS.

    `local_align`'s argument exactly: a stylesheet error names a line the
    caller never wrote.
    """
    for bad in (0, -1, "2", 1.5, True):
        with pytest.raises(ValueError, match="scrollbar_size"):
            ChatStyle(scrollbar_size=bad)


async def _scrollbar_column(app, pilot):
    """Every background colour painted down the scrollbar's own column."""
    for i in range(14):
        await app.say("mensagem %d" % i)
    await pilot.pause()
    log = app._chat_log
    log.scroll_to(y=6, animate=False)
    await pilot.pause()
    await pilot.pause()
    assert log.show_vertical_scrollbar, "narrow and full: the bar is up to be looked at"
    bar = log.vertical_scrollbar
    return log, bar, lambda: {app.screen.get_style_at(bar.region.x, y).bgcolor.name
                              for y in range(bar.region.y, bar.region.bottom)}


async def test_the_track_is_the_chat_behind_it_until_you_reach_for_it():
    """One cell is the floor, so the thinning left is what the cell is painted with.

    A track in a colour of its own is a strip down the whole height of the
    chat whether or not anyone is scrolling. `transparent` leaves the thumb
    alone at rest, and the hover colour brings the track back under the
    pointer — so nothing is lost, it is only quiet.
    """
    app = await chat_app()
    async with app.run_test(size=(48, 14)) as pilot:
        _, bar, painted = await _scrollbar_column(app, pilot)
        style = ChatStyle()

        assert painted() == {style.chat_bg}, "at rest the column is chat, not a strip"

        bar.mouse_over = True
        await pilot.pause()
        await pilot.pause()
        assert painted() == {style.scrollbar_hover_bg}, "and the track is there when reached for"


async def test_a_transparent_track_follows_the_chat_background():
    """Which is why it is `transparent` and not `chat_bg`'s hex written twice.

    Textual composites a translucent scrollbar background onto the parent's,
    so recolouring the chat carries the track with it. Spelling the hex again
    would leave a strip behind the moment someone changed one of the two.
    """
    style = replace(ChatStyle(), chat_bg="#101010", screen_bg="#101010")
    app = await chat_app(style=style)
    async with app.run_test(size=(48, 14)) as pilot:
        _, _, painted = await _scrollbar_column(app, pilot)
        assert painted() == {"#101010"}


async def _both_bars_up(pilot, app):
    """A log long enough and an input tall enough that both bars are drawn."""
    for i in range(20):
        await app.say("mensagem %d" % i)
    await pilot.pause()
    inp = app.query_one("#input-line", CommandInput)
    inp.text = "\n".join("linha %d" % i for i in range(20))
    await pilot.pause()
    await pilot.pause()
    log = app._chat_log
    assert log.show_vertical_scrollbar and inp.show_vertical_scrollbar, \
        "the premise: both are scrolling"
    return log, inp


async def test_the_input_scrollbar_wears_the_same_palette_as_the_log():
    """The input is a TextArea with a bar of its own, and nothing named it.

    It wore Textual's default — two cells of dark blue — beside a one-cell
    grey one, which is the same silence the dead `.scrollbar` rule kept. Both
    selectors share one rule now, so the two cannot drift; the assertions go
    against `ChatStyle` and not against each other, or two identically wrong
    bars would pass.
    """
    style = ChatStyle()
    app = await chat_app()
    async with app.run_test(size=(44, 18)) as pilot:
        log, inp = await _both_bars_up(pilot, app)

        for who, widget in (("log", log), ("input", inp)):
            assert widget.scrollbar_size_vertical == style.scrollbar_size, \
                "%s: one cell, not Textual's two" % who
            assert widget.styles.scrollbar_color == Color.parse(style.scrollbar_color), \
                "%s: the palette's thumb, not the theme's blue" % who
            assert widget.styles.scrollbar_background == Color.parse(style.scrollbar_bg), \
                "%s: the track is the chat behind it" % who


async def test_both_scrollbars_line_up_against_the_edge():
    """One column down the right side, not two bars in two places.

    A scrollbar is inset by its widget's *right padding*, which is what the
    two had different amounts of — so zeroing both is what aligns them and
    what puts them against the edge at the same time. Measured, not assumed:
    at 44 columns the last one is 43.
    """
    app = await chat_app()
    async with app.run_test(size=(44, 18)) as pilot:
        log, inp = await _both_bars_up(pilot, app)

        assert log.vertical_scrollbar.region.x == inp.vertical_scrollbar.region.x, \
            "the two bars are in the same column"
        assert log.vertical_scrollbar.region.x == 44 - log.scrollbar_size_vertical, \
            "and that column is the last one in the window"


async def test_a_bubble_never_runs_past_the_window_or_under_the_scrollbar():
    """bubble_max_width is a cap, not a width: a narrow window wins over it."""
    app = await chat_app()
    async with app.run_test(size=(60, 14)) as pilot:
        for i in range(6):
            await app.say("mensagem %d, comprida o suficiente para encher a linha toda" % i)
        await pilot.pause()

        log = app._chat_log
        assert log.show_vertical_scrollbar, "narrow and full: the scrollbar is up"

        edges = [w.region.x + w.region.width for w in app.query(".message-bubble")]
        assert max(edges) <= 60 - log.scrollbar_size_vertical, \
            "a bubble stops at the scrollbar rather than running under it"

        # Measured on the widget, not inferred from a coordinate: without the
        # rule the bubble still clears the scrollbar by the log's own padding,
        # so an edge test passes either way and guards nothing.
        margin = int(ChatStyle().bubble_margin_right)
        assert all(c.styles.margin.right == margin
                   for c in app.query(".message-container")), \
            "and keeps a margin between the two"


async def test_selecting_a_bubble_fills_it_and_nothing_else():
    """The fill is the whole of the selection; there is no second outline."""
    app = await chat_app()
    async with app.run_test() as pilot:
        await app.say("oi")
        await pilot.pause()

        bubble = _bubbles(app)[0]
        app._chat_log.set_reply_target(app.messages[0].id)
        await pilot.pause()

        assert bubble.styles.background.a > 0, "filled"
        assert not bubble.styles.outline.spacing, "and not also outlined"


# === The header sits above the bubble, in the peer's colour =====================


async def test_the_header_is_above_the_bubble_and_outside_it():
    """It is a sibling of the bubble, not a child: the bubble holds only text."""
    app = await chat_app()
    async with app.run_test(size=(80, 24)) as pilot:
        await app.say("oi")
        await pilot.pause()

        container = app._chat_log._msg_widgets[app.messages[0].id]
        header = container.query_one(".message-header")
        bubble = container.query_one(".message-bubble")

        assert header.parent is container, "a sibling of the bubble"
        assert header not in bubble.children, "and not inside it"
        assert header.region.y < bubble.region.y, "drawn above it"


async def test_the_bubble_border_is_the_headers_colour():
    """One colour per peer, not one for the name and another for the box."""
    app = await chat_app(connectors=[_Outro()])
    async with app.run_test(size=(80, 24)) as pilot:
        at = {getattr(who, "name", None): i for i, who in app.peers().items()}
        await app.say("eu")
        await app.ask(at["outro"], "e tu?")
        await pilot.pause()

        pairs = set()
        for container in app._chat_log._msg_widgets.values():
            header = container.query_one(".message-header")
            border = container.query_one(".message-bubble").styles.border.top
            assert str(header.styles.color) == str(border[1]), "border matches the header"
            pairs.add(str(header.styles.color))

        assert len(pairs) > 1, "and the two peers are not the same colour"


async def test_a_bubble_is_never_narrower_than_the_header_above_it():
    """The header sits on top of the bubble, so the bubble has to reach it.

    A two-word message would otherwise get a bubble far narrower than its own
    header, which reads as two things rather than one.
    """
    app = await chat_app()
    async with app.run_test(size=(80, 24)) as pilot:
        await app.say("oi")
        await app.say("uma mensagem bem mais comprida do que o seu cabeçalho, para variar")
        await pilot.pause()

        for container in app._chat_log._msg_widgets.values():
            header = container.query_one(".message-header")
            bubble = container.query_one(".message-bubble")
            assert bubble.region.width >= header.region.width, \
                "the bubble covers its header, whatever it says"


# === A key the terminal swallows is refused =====================================


@pytest.mark.parametrize("combo, arrives", [
    ("ctrl+h", "backspace"),        # what made ctrl+h fail on Termux
    ("ctrl+i", "tab"),
    ("ctrl+m", "enter"),
    ("ctrl+[", "escape"),
])
async def test_a_quit_key_the_terminal_cannot_send_is_refused(combo, arrives):
    """A terminal sends one byte for these and for the key they alias.

    Textual reports the alias, so the binding never fires — which is the same
    silent nothing `_validate_key` already existed to prevent.
    """
    with pytest.raises(ValueError, match=arrives):
        await chat_app(quit_key=combo)


def test_the_swallowed_keys_are_read_from_textual_not_listed_here():
    """Derived, so it cannot drift from what Textual actually does."""
    from chatinho.chat_app import _SWALLOWED, _swallowed_keys

    assert _swallowed_keys() == _SWALLOWED
    assert _SWALLOWED["ctrl+h"] == "backspace"
    assert "ctrl+g" not in _SWALLOWED, "still a usable quit key"


# === Holding a message copies it ================================================


async def test_two_taps_copy_the_message():
    app = await chat_app()
    async with app.run_test(size=(80, 24)) as pilot:
        await app.say("para copiar")
        await pilot.pause()

        copied = []
        app.copy_to_clipboard = copied.append

        container = app._chat_log._msg_widgets[app.messages[0].id]
        await pilot.click(container)
        await pilot.click(container)
        await pilot.pause()

        assert copied == ["para copiar"]
        assert app._chat_log.reply_target is None, \
            "the second tap puts the selection back: a double tap only copies"


async def test_one_tap_still_selects_the_reply_target():
    app = await chat_app()
    async with app.run_test(size=(80, 24)) as pilot:
        await app.say("para responder")
        await pilot.pause()

        copied = []
        app.copy_to_clipboard = copied.append

        container = app._chat_log._msg_widgets[app.messages[0].id]
        await pilot.click(container)
        await pilot.pause()

        assert copied == [], "one tap copies nothing"
        assert app._chat_log.reply_target == app.messages[0].id


def _press_at(widget, screen_y, screen_x=None):
    """A MouseDown on *widget*, landing at *screen_y*."""
    return events.MouseDown(widget, 0, 0, 0, 0, 1, False, False, False,
                            screen_x=widget.region.x if screen_x is None else screen_x,
                            screen_y=screen_y)


def _click_at(widget, screen_y, screen_x=None):
    """The Click Textual synthesises when the release lands at *screen_y*.

    Built by hand because ``pilot.mouse_down``/``mouse_up`` do not produce one
    — Textual synthesises a Click in the app, from a release on the widget the
    press landed on — and ``pilot.click`` presses and releases in one spot, so
    neither can express a press that travelled. A drag test driven by the
    pilot passed with the guard removed, because nothing was reaching the
    handler at all.
    """
    return events.Click(widget, 0, 0, 0, 0, 1, False, False, False,
                        screen_x=widget.region.x if screen_x is None else screen_x,
                        screen_y=screen_y)


async def test_a_press_that_travelled_down_is_not_a_tap():
    """A press that landed low and lifted high was a drag, not a tap."""
    app = await chat_app()
    async with app.run_test(size=(80, 24)) as pilot:
        await app.say("nem copiar nem responder")
        await pilot.pause()

        container = app._chat_log._msg_widgets[app.messages[0].id]
        here = container.region.y
        container.on_mouse_down(_press_at(container, here + 10))   # landed low
        container.on_click(_click_at(container, here))             # lifted high
        await pilot.pause()

        assert app._chat_log.reply_target is None, "a drag selects nothing"


async def test_a_tap_that_barely_moves_is_still_a_tap():
    """A finger is never perfectly still; only a real travel is a scroll."""
    app = await chat_app()
    async with app.run_test(size=(80, 24)) as pilot:
        await app.say("ainda e um toque")
        await pilot.pause()

        container = app._chat_log._msg_widgets[app.messages[0].id]
        here = container.region.y
        container.on_mouse_down(_press_at(container, here + 1))
        container.on_click(_click_at(container, here))
        await pilot.pause()

        assert app._chat_log.reply_target == app.messages[0].id


# === A drag is a selection, unless it started where there is nothing to select ===


def _mouse(cls, x, y, button=1):
    """A raw mouse event in *screen* coordinates, for the screen to route.

    The pilot cannot express this: it presses and releases in one spot, and
    what is under test here is a press that travels across widgets.
    """
    return cls(None, x, y, 0, 0, button, False, False, False, screen_x=x, screen_y=y)


def _a_cell_holding_text(screen, log):
    """The first coordinate in *log* that has selectable content under it.

    ``get_widget_and_offset_at`` reports no offset where there is nothing to
    select, which is the whole of what tells a pan from a selection.
    """
    region = log.content_region
    for y in range(region.y, region.bottom):
        for x in range(region.x, region.right):
            widget, offset = screen.get_widget_and_offset_at(x, y)
            if offset is not None and type(widget).__name__ == "MarkdownParagraph":
                return x, y
    raise AssertionError("no text in the log to press on")


async def _a_full_log(pilot, app, count=30):
    """Enough messages that the log scrolls, parked away from either end."""
    for i in range(count):
        await app.say("mensagem %d com algum texto para encher a bolha" % i)
    await pilot.pause()
    log = app._chat_log
    log.scroll_to(y=log.max_scroll_y // 2, animate=False)
    await pilot.pause()
    await pilot.pause()
    return log


async def test_dragging_across_text_selects_it_and_the_log_holds_still():
    """The reported bug: selecting across a bubble made the scroll shake.

    Two things read the same drag. From Textual 3 a mouse drag is a text
    selection, started by the screen before the event reaches any widget, and
    the log was panning on the same one — so the text slid out from under the
    selection while the selection reached after it. A terminal cannot tell the
    two gestures apart by device, because no mouse protocol reports one: what
    decides is whether the press landed on anything selectable.
    """
    app = await chat_app()
    async with app.run_test(size=(80, 24)) as pilot:
        log    = await _a_full_log(pilot, app)
        screen = app.screen
        x, y   = _a_cell_holding_text(screen, log)

        parked = int(log.scroll_offset.y)
        screen._forward_event(_mouse(events.MouseDown, x, y))
        await pilot.pause()
        for below in range(y + 1, y + 6):
            screen._forward_event(_mouse(events.MouseMove, x, below))
            await pilot.pause()
            assert int(log.scroll_offset.y) == parked, \
                "the log moved under the selection — that is the shake"

        assert screen.get_selected_text(), "and the drag selected the text it crossed"


async def test_dragging_the_background_still_pans_the_log():
    """A drag with nothing to select under it is still how the log is panned.

    A finger and a mouse arrive as the same bytes, so the touch gesture cannot
    be kept by asking which device sent it. It is kept by where it starts: the
    margin beside a bubble has no text in it.
    """
    app = await chat_app()
    async with app.run_test(size=(80, 24)) as pilot:
        log    = await _a_full_log(pilot, app)
        screen = app.screen
        x      = log.content_region.x          # left of the right-aligned bubbles
        top    = log.content_region.y + 4
        assert screen.get_widget_and_offset_at(x, top)[1] is None, \
            "the margin is the background, or this test is pressing on a bubble"

        parked = int(log.scroll_offset.y)
        screen._forward_event(_mouse(events.MouseDown, x, top))
        await pilot.pause()
        travelled = 5
        for below in range(top + 1, top + 1 + travelled):
            screen._forward_event(_mouse(events.MouseMove, x, below))
            await pilot.pause()

        # Cell for cell, and that is the second half of the bug: the drag used
        # to be measured in `event.y`, which is relative to whatever descendant
        # the pointer is over *now* — a different one on every report, once the
        # log started moving. Five cells of travel moved the log two.
        assert int(log.scroll_offset.y) == parked - travelled, \
            "the pan follows the pointer cell for cell"
        assert screen.get_selected_text() is None, "and a pan selects nothing"


async def test_selecting_sideways_does_not_retarget_the_reply():
    """Textual makes a Click from any release on the widget the press landed on.

    Dragging across a line to select a few words never moves a row, so the
    guard that watched only `screen_y` let it through as a tap — and the tap
    silently moved the reply target. A press that travelled on either axis is
    a drag.
    """
    app = await chat_app()
    async with app.run_test(size=(80, 24)) as pilot:
        await app.say("uma mensagem com palavras que se seleccionam")
        await pilot.pause()

        container = app._chat_log._msg_widgets[app.messages[0].id]
        here      = container.region.y
        left      = container.region.x
        container.on_mouse_down(_press_at(container, here, screen_x=left))
        container.on_click(_click_at(container, here, screen_x=left + 12))
        await pilot.pause()

        assert app._chat_log.reply_target is None, "a sideways drag selects text, not a message"


async def test_the_header_stays_inside_a_phone_width_terminal():
    """`_bubble_width` caps at `bubble_max_width`, which is 72 — wider than a phone.

    The bubble survives that because `max-width: 100%` clamps it; the header
    was given the same measured span and nothing to clamp it with, so its box
    ran past the log and the right-aligned text inside it landed off-screen
    entirely. CLAUDE.md already records this exact failure for the bubble —
    "a cap in cells is not a width" — and the header never got the fix.

    The one other test of the header runs at 96 columns, where the bubble is
    narrower than the terminal and nothing overflows, so the suite never saw
    it.
    """
    for width in (40, 50, 60):
        app = await chat_app()
        async with app.run_test(size=(width, 16)) as pilot:
            await app.say("uma mensagem bastante longa para encher a bolha toda")
            await pilot.pause()

            log       = app._chat_log
            container = log._msg_widgets[app.messages[0].id]
            start, end = _header_text_span(container)

            assert end <= log.content_region.right, \
                "at %d columns the header ran past the log" % width
            assert start >= log.content_region.x, \
                "at %d columns the header started before the log" % width


async def test_selecting_one_character_is_not_a_tap_either():
    """`_A_DRAG` has to allow a cell of wobble, so it cannot catch a short drag.

    Textual clears the selection when the press and the release share a cell,
    so a selection the screen is *still holding* at click time means the
    pointer dragged across text — which a travel threshold generous enough for
    a thumb will always let through.
    """
    app = await chat_app()
    async with app.run_test(size=(80, 16)) as pilot:
        await app.say("uma mensagem com varias palavras")
        await pilot.pause()

        log, screen = app._chat_log, app.screen
        x, y = _a_cell_holding_text(screen, log)

        screen._forward_event(_mouse(events.MouseDown, x, y))
        await pilot.pause()
        screen._forward_event(_mouse(events.MouseMove, x + 1, y))
        await pilot.pause()
        screen._forward_event(_mouse(events.MouseUp, x + 1, y, button=0))
        await pilot.pause()

        assert screen.get_selected_text(), "the premise: one cell did select something"

        container = log._msg_widgets[app.messages[0].id]
        container.on_mouse_down(_mouse(events.MouseDown, x, y))
        container.on_click(_mouse(events.Click, x + 1, y))
        await pilot.pause()

        assert log.reply_target is None, "a selection, however short, is not a tap"


async def test_a_tap_that_selects_nothing_still_taps():
    """And the guard above must not eat the gesture it sits in front of."""
    app = await chat_app()
    async with app.run_test(size=(80, 16)) as pilot:
        await app.say("uma mensagem com varias palavras")
        await pilot.pause()

        log, screen = app._chat_log, app.screen
        x, y = _a_cell_holding_text(screen, log)

        screen._forward_event(_mouse(events.MouseDown, x, y))
        await pilot.pause()
        screen._forward_event(_mouse(events.MouseUp, x, y, button=0))
        await pilot.pause()

        assert screen.get_selected_text() is None, \
            "the premise: pressing and lifting in one cell selects nothing"

        container = log._msg_widgets[app.messages[0].id]
        container.on_mouse_down(_mouse(events.MouseDown, x, y))
        container.on_click(_mouse(events.Click, x, y))
        await pilot.pause()

        assert log.reply_target == app.messages[0].id


# === The input is ruled off, not boxed in ========================================


async def test_the_input_is_ruled_off_above_and_below_with_open_sides():
    """Two lines, not a bubble: the sides were costing the text two columns.

    A box is a widget sitting in the chat; a rule above and below is somewhere
    to write. On a phone those two columns are the difference, which is why
    the content width is asserted and not only the border type — a `border:
    none` that forgot the rules would pass a type check on top and bottom.
    """
    app = await chat_app()
    async with app.run_test(size=(46, 14)) as pilot:
        await pilot.pause()

        inp = app.query_one("#input-line", CommandInput)
        assert inp.styles.border_top[0]    == "solid", "a rule above"
        assert inp.styles.border_bottom[0] == "solid", "and below"
        assert inp.styles.border_left[0]   == "", "and nothing at the sides"
        assert inp.styles.border_right[0]  == ""
        # 46 columns, less the one cell of padding on the left and no border
        # either side. There is no padding on the right: that is what the
        # scrollbar is inset by, and zeroing it is what puts the bar against
        # the edge in the same column as the log's. The box below takes two
        # more columns for its sides.
        assert inp.content_region.width == 45, "so the text keeps the side columns"


async def test_the_rules_brighten_while_the_input_has_focus():
    """`_input_frame_rules` writes the colour twice, once per state.

    Wiring both to one colour is the easy slip, and it is invisible until you
    look away from the input — which nothing else in the suite does. Focus
    really does leave: Tab moves it to the log.

    The two colours are asserted to differ first, or this passes on a palette
    that made them the same and the whole check would be vacuous.
    """
    app = await chat_app()
    async with app.run_test(size=(46, 14)) as pilot:
        await pilot.pause()
        style = ChatStyle()
        assert style.input_focus_border != style.input_border, \
            "the premise: the two states are meant to look different"

        inp = app.query_one("#input-line", CommandInput)
        assert inp.has_focus, "and the input holds focus at rest"
        assert inp.styles.border_top[1] == Color.parse(style.input_focus_border)

        app.set_focus(None)
        await pilot.pause()
        assert inp.styles.border_top[1] == Color.parse(style.input_border), \
            "and drops back to the resting colour when it loses focus"


async def test_the_input_rules_carry_no_hue_of_their_own():
    """Two orange bars across the width is not an accent, it is a stripe.

    The accent stays on the quote border and the popup's highlighted row,
    where it marks one thing rather than framing the whole screen.
    """
    style = ChatStyle()
    for colour in (style.input_border, style.input_focus_border):
        red, green, blue = Color.parse(colour).rgb
        assert max(red, green, blue) - min(red, green, blue) <= 8, \
            "%s is a hue, not a grey" % colour
    assert style.accent != style.input_focus_border, "the accent is not the input's"


async def test_the_box_is_still_there_for_whoever_prefers_it():
    """Both shapes are real; `input_frame` is which one."""
    app = await chat_app(style=replace(ChatStyle(), input_frame="box"))
    async with app.run_test(size=(46, 14)) as pilot:
        await pilot.pause()

        inp = app.query_one("#input-line", CommandInput)
        edges = (inp.styles.border_top, inp.styles.border_bottom,
                 inp.styles.border_left, inp.styles.border_right)
        assert [e[0] for e in edges] == ["round"] * 4, "boxed in on all four sides"
        assert inp.content_region.width == 43, "which costs the two side columns"


def test_a_frame_that_is_neither_shape_is_refused_at_construction():
    """`local_align`'s argument again: Textual reports a broken rule nowhere useful."""
    for bad in ("round", "none", "", None):
        with pytest.raises(ValueError, match="input_frame"):
            ChatStyle(input_frame=bad)


# === The header names who spoke =================================================


async def test_the_header_names_the_peer_with_an_at_and_no_brackets():
    """`Other` told you nothing when two connectors were in the room."""
    app = await chat_app(connectors=[_Outro()], commands=[_Eco()])
    async with app.run_test(size=(90, 24)) as pilot:
        at = {getattr(who, "name", None): i for i, who in app.peers().items()}
        await app.say("eu")
        await app.ask(at["outro"], "e tu?")
        await app.command("eco", "ola")
        await pilot.pause()

        by_id = {m.id: m for m in app.messages}
        named = {}
        for msg_id, container in app._chat_log._msg_widgets.items():
            named[by_id[msg_id].frm] = str(container.query_one(".message-header").render())

        assert named[LOCAL].startswith(app.messages[0].timestamp.strftime("%H:%M")), \
            "the time leads, without its brackets"
        assert "[" not in named[LOCAL] and "]" not in named[LOCAL]
        assert "@chat" in named[LOCAL], "the terminal's own name"
        assert "@outro" in named[at["outro"]], "and the connector's"
        assert "@tool" in named[TOOL], "a command is named outright: it is in no roster"


async def test_a_peer_that_is_gone_is_named_by_its_number():
    """History outlives connectors: a backend reloads what a peer once said."""
    app = await chat_app()
    async with app.run_test(size=(90, 24)):
        assert app._chat_log._name_of_peer(41) == "41", "still true, still distinct"


async def test_the_terminal_can_be_named_something_you_would_call_yourself():
    """`@chat` is the class's own name; `@me` is what a person types."""
    app = await chat_app(name="me")
    async with app.run_test(size=(90, 24)) as pilot:
        await app.say("eu")
        await pilot.pause()

        container = app._chat_log._msg_widgets[app.messages[0].id]
        assert "@me" in str(container.query_one(".message-header").render())


async def test_naming_the_terminal_is_optional_and_defaults_to_the_class():
    app = await chat_app()
    async with app.run_test(size=(90, 24)) as pilot:
        await app.say("eu")
        await pilot.pause()

        container = app._chat_log._msg_widgets[app.messages[0].id]
        assert "@chat" in str(container.query_one(".message-header").render())


async def test_a_blank_terminal_name_is_refused():
    """It is shown as `@name`: a blank one renders a lone `@`."""
    with pytest.raises(ValueError, match="blank"):
        await chat_app(name="   ")


def test_naming_an_instance_works_only_because_the_decorator_shadows_the_property():
    """DOMNode.name is read-only; @frontend's class attribute is what allows this.

    Worth a test of its own: the same assignment on a plain App raises, so
    dropping the decorator's `cls.name` would break naming with no other sign.
    """
    from textual.app import App

    class Plain(App):
        pass

    with pytest.raises(AttributeError):
        Plain().name = "me"

    assert ChatApp.__dict__.get("name") == "chat", "the decorator wrote it onto the class"


# === What the bubble costs around its text ======================================


async def test_the_bubble_clears_its_header_by_a_space():
    """Flush with the header reads as one block; a space apart reads as two."""
    app = await chat_app()
    async with app.run_test(size=(90, 24)) as pilot:
        await app.say("oi")
        await pilot.pause()

        container = app._chat_log._msg_widgets[app.messages[0].id]
        header = container.query_one(".message-header")
        bubble = container.query_one(".message-bubble")
        assert bubble.region.width == header.region.width + 2, \
            "the header's own indent, plus one space after it"


async def test_a_line_measured_to_fit_does_not_wrap():
    """Markdown carries `padding: 0 2 0 2` of its own, inside what we measured.

    Four cells the bubble's width never counted, so a line sized to fit wrapped
    anyway. The stylesheet zeroes it rather than the measurement adding four.
    """
    app = await chat_app()
    async with app.run_test(size=(100, 24)) as pilot:
        one_line = "abcdefghij " * 3 + "fim"
        await app.say(one_line)
        await pilot.pause()

        container = app._chat_log._msg_widgets[app.messages[0].id]
        body = container.query_one(".message-body")
        assert body.region.height == 1, "one line of text takes one row"
        assert body.styles.padding.right == 0, "and Markdown adds no padding of its own"


async def test_there_is_one_blank_row_under_the_text_not_two():
    """The bubble pads by one; MarkdownParagraph added a second underneath."""
    app = await chat_app()
    async with app.run_test(size=(90, 24)) as pilot:
        await app.say("oi")
        await pilot.pause()

        container = app._chat_log._msg_widgets[app.messages[0].id]
        bubble = container.query_one(".message-bubble")
        # border(2) + padding(1 above, 1 below) + one row of text
        assert bubble.region.height == 5


async def test_paragraphs_are_still_separated_from_each_other():
    """Only the *trailing* margin goes: `:last-child`, not every paragraph."""
    app = await chat_app()
    async with app.run_test(size=(90, 40)) as pilot:
        await app.say("um\n\ndois\n\ntres")
        await pilot.pause()

        body = app._chat_log._msg_widgets[app.messages[0].id].query_one(".message-body")
        margins = [block.styles.margin.bottom for block in body.children]
        assert margins == [1, 1, 0], "separated, but nothing trailing the last"


async def test_one_blank_row_separates_one_message_from_the_next():
    app = await chat_app()
    async with app.run_test(size=(90, 40)) as pilot:
        await app.say("primeira")
        await app.say("segunda")
        await pilot.pause()

        first, second = list(app._chat_log._msg_widgets.values())
        below = first.query_one(".message-bubble").region
        assert second.region.y - (below.y + below.height) == 1


# === Copying without the gesture ================================================


async def test_the_copy_key_copies_the_selected_message():
    """A phone terminal may take the long press for its own menu."""
    app = await chat_app()
    async with app.run_test(size=(90, 24)) as pilot:
        await app.say("para copiar")
        await pilot.pause()

        copied = []
        app.copy_to_clipboard = copied.append

        app._chat_log.set_reply_target(app.messages[0].id)
        await pilot.press("ctrl+y")
        await pilot.pause()

        assert copied == ["para copiar"]


async def test_the_copy_key_says_what_to_do_when_nothing_is_selected():
    app = await chat_app()
    async with app.run_test(size=(90, 24)) as pilot:
        await app.say("nada selecionado")
        await pilot.pause()

        copied = []
        app.copy_to_clipboard = copied.append
        told = []
        app.notify = lambda message, **kw: told.append(message)

        await pilot.press("ctrl+y")
        await pilot.pause()

        assert copied == []
        assert told and "Select a message first" in told[0]


async def test_the_copy_key_can_be_moved_and_is_validated_like_the_quit_key():
    app = await chat_app(copy_key="f8")
    async with app.run_test(size=(90, 24)) as pilot:
        await app.say("noutra tecla")
        await pilot.pause()

        copied = []
        app.copy_to_clipboard = copied.append
        app._chat_log.set_reply_target(app.messages[0].id)
        await pilot.press("f8")
        await pilot.pause()

        assert copied == ["noutra tecla"]

    with pytest.raises(ValueError, match="backspace"):
        await chat_app(copy_key="ctrl+h")


async def test_copying_takes_both_routes_and_names_them(monkeypatch):
    """OSC 52 goes out regardless; a helper runs too when the system has one."""
    from chatinho import chat_clipboard

    monkeypatch.setattr(chat_clipboard, "put", lambda text: "termux-clipboard-set")

    app = await chat_app()
    async with app.run_test(size=(90, 24)) as pilot:
        await app.say("para copiar")
        await pilot.pause()

        osc52 = []
        app.copy_to_clipboard = osc52.append
        told = []
        app.notify = lambda message, **kw: told.append(message)

        app._chat_log.set_reply_target(app.messages[0].id)
        await pilot.press("ctrl+y")
        for _ in range(10):
            await pilot.pause()
            if told:
                break

        assert osc52 == ["para copiar"], "the escape sequence went out"
        assert told and "OSC 52 + termux-clipboard-set" in told[0], "and both are named"
        assert "para copiar" in told[0], "and the confirmation shows what was copied"


async def test_with_no_helper_the_notification_says_only_osc_52(monkeypatch):
    """Naming the route is what makes a silent failure diagnosable."""
    from chatinho import chat_clipboard

    monkeypatch.setattr(chat_clipboard, "put", lambda text: None)

    app = await chat_app()
    async with app.run_test(size=(90, 24)) as pilot:
        await app.say("sem helper")
        await pilot.pause()

        app.copy_to_clipboard = lambda text: None
        told = []
        app.notify = lambda message, **kw: told.append(message)

        app._chat_log.set_reply_target(app.messages[0].id)
        await pilot.press("ctrl+y")
        for _ in range(10):
            await pilot.pause()
            if told:
                break

        assert told and told[0].endswith("Sent by OSC 52.")


async def test_two_taps_far_apart_in_time_are_two_taps():
    """The pair has to be quick, or every second reply-select would copy."""
    app = await chat_app()
    async with app.run_test(size=(80, 24)) as pilot:
        await app.say("nem copiar")
        await pilot.pause()

        copied = []
        app.copy_to_clipboard = copied.append

        container = app._chat_log._msg_widgets[app.messages[0].id]
        await pilot.click(container)
        # Wound back past any plausible threshold rather than by a multiple of
        # the constant: a test measured against the value it guards holds at
        # every value, and notices none of them changing.
        container._last_tap_at -= 3600
        await pilot.click(container)
        await pilot.pause()

        assert copied == [], "two separate taps copy nothing"


async def test_the_confirmation_is_a_popup_that_actually_appears(monkeypatch):
    """The one that matters, and the one nothing was checking.

    ``run_test`` disables notifications by default, so every other test here
    asserts on ``notify`` being *called*. This one turns them on and looks for
    the widget, because "it was called" is not "the user saw it".
    """
    from textual.widgets._toast import Toast

    from chatinho import chat_clipboard
    monkeypatch.setattr(chat_clipboard, "put", lambda text: "termux-clipboard-set")

    app = await chat_app()
    async with app.run_test(size=(80, 24), notifications=True) as pilot:
        await app.say("para copiar")
        await pilot.pause()

        app._chat_log.set_reply_target(app.messages[0].id)
        await pilot.press("ctrl+y")

        toasts = []
        for _ in range(20):
            await pilot.pause()
            toasts = list(app.screen.query(Toast))
            if toasts:
                break

        assert toasts, "a toast is mounted on the screen"
        assert toasts[0].region.width > 0 and toasts[0].display, "and it is drawn"


def test_the_confirmation_shows_what_was_copied_on_one_line():
    """A phone cannot check the clipboard without leaving the chat."""
    assert preview_of("uma linha") == "uma linha"
    assert preview_of("com\nquebras\ne   espaços") == "com quebras e espaços"

    long = "palavra " * 40
    shown = preview_of(long)
    assert len(shown) == 60 and shown.endswith("…")


def test_the_double_tap_does_not_use_textuals_chain_count():
    """Textual counts a double click only on the *exact same cell*.

    That is right for a mouse and wrong for a thumb, which is the whole reason
    this was asked for — so the tolerance is ours, and wider than Textual's in
    both time and position. A test says so, because reaching for `event.chain`
    later would look like a simplification and would quietly stop working on
    the device this exists for.
    """
    from textual.app import App

    import chatinho.chat_log as log

    assert "chain" not in inspect.getsource(log._MessageContainer.on_click).replace(
        "``event.chain``", ""
    ).replace("chain count", ""), "the chain count is not what decides"
    assert log._A_DOUBLE > App.CLICK_CHAIN_TIME_THRESHOLD, "longer than a mouse's"
    assert log._A_WOBBLE >= 1, "and a cell of slack, which Textual allows none of"


# === Where the chat sits, and which side you are on =============================


def _sides(app):
    """Where each bubble starts, by who spoke."""
    out = {}
    for container in app.query(".message-container"):
        who = "sent" if "sent" in container.classes else "received"
        out.setdefault(who, container.query_one(".message-bubble").region.x)
    return out


def _header_text_span(container):
    """The columns the header's *text* occupies, not the box holding it.

    The box spans the bubble on both sides now, so a box measurement would
    pass with the text stranded at either end of it. This renders the header
    and finds where the ink actually is.
    """
    header = container.query_one(".message-header")
    line   = header.render_lines(header.region.size.region)[0].text
    return (header.region.x + len(line) - len(line.lstrip()),
            header.region.x + len(line.rstrip()))


async def test_the_chat_is_centred_and_capped_on_a_wide_terminal():
    """A line the width of a desk is a line nobody reads across."""
    app = await chat_app()
    async with app.run_test(size=(140, 20)) as pilot:
        await app.say("oi")
        await pilot.pause()

        body = app.query_one("#chat-body")
        cap  = int(ChatStyle().chat_max_width)
        assert body.region.width == cap, "capped at chat_max_width"
        assert body.region.x == (140 - cap) // 2, "and centred in what is left"


async def test_a_narrow_terminal_gives_the_chat_all_of_it():
    """The cap is a maximum, not a width: nothing is wasted on a phone."""
    app = await chat_app()
    async with app.run_test(size=(60, 20)) as pilot:
        await app.say("oi")
        await pilot.pause()

        body = app.query_one("#chat-body")
        assert (body.region.x, body.region.width) == (0, 60)


async def test_the_input_is_still_at_the_bottom_of_the_centred_body():
    """`dock: bottom` is relative to the parent, which is now a narrower one."""
    app = await chat_app()
    async with app.run_test(size=(140, 20)) as pilot:
        await app.say("oi")
        await pilot.pause()

        body  = app.query_one("#chat-body")
        input = app.query_one("#input-area")
        # The premise first, or this passes for the wrong reason: with no
        # centring at all the input is still at the bottom of a full-width
        # screen, and every assertion below holds while guarding nothing.
        assert body.region.width < 140, "the body really is narrower than the screen"
        assert input.region.y + input.region.height == body.region.y + body.region.height
        assert input.region.x == body.region.x, "and the input moved in with it"


async def test_your_own_messages_are_on_the_right_by_default():
    """Everyone else stays left, so it reads as two columns."""
    app = await chat_app(connectors=[_Outro()])
    async with app.run_test(size=(140, 20)) as pilot:
        at = {getattr(who, "name", None): i for i, who in app.peers().items()}
        await app.say("minha")
        await app.ask(at["outro"], "tua?")
        await pilot.pause()

        sides = _sides(app)
        assert sides["sent"] > sides["received"], "yours are on the right"
        assert sides["received"] == app.query_one("#chat-body").region.x + 2, \
            "and theirs are not"


async def test_a_header_hugs_the_same_edge_its_bubble_does():
    """Textual's ``align`` moves the header and the bubble as one block.

    It does not align *within* that block, so a header left to size itself
    stays against the bubble's left edge whichever side the block landed on —
    which on the right, under a wide bubble, strands it a whole bubble away
    from the message it names. The header takes the bubble's own span now, and
    the text inside it takes the same side.
    """
    app = await chat_app(connectors=[_Outro()])
    async with app.run_test(size=(96, 24)) as pilot:
        at = {getattr(who, "name", None): i for i, who in app.peers().items()}
        await app.say("uma mensagem longa o suficiente para a bolha esticar bem para a esquerda")
        await app.ask(at["outro"], "e uma pergunta igualmente comprida, para a bolha dela esticar")
        await pilot.pause()

        mine   = app.query_one(".message-container.sent")
        theirs = app.query_one(".message-container.received")

        bubble = mine.query_one(".message-bubble").region
        start, end = _header_text_span(mine)
        assert end == bubble.right - 1, "mine ends where its bubble does, a cell inside the border"
        assert start > bubble.x + 10, "and is not stranded at the far end of it"

        bubble = theirs.query_one(".message-bubble").region
        start, end = _header_text_span(theirs)
        assert start == bubble.x + 1, "theirs starts where its bubble does, a cell inside"
        assert end < bubble.right - 10, "and is not dragged over to the other end"


async def test_local_align_left_puts_everyone_in_one_column():
    app = await chat_app(connectors=[_Outro()],
                         style=replace(ChatStyle(), local_align="left"))
    async with app.run_test(size=(140, 20)) as pilot:
        at = {getattr(who, "name", None): i for i, who in app.peers().items()}
        await app.say("minha")
        await app.ask(at["outro"], "tua?")
        await pilot.pause()

        sides = _sides(app)
        assert sides["sent"] == sides["received"], "one column"


def test_a_local_align_that_is_not_a_side_is_refused():
    """Textual would take a broken rule and report it nowhere useful."""
    with pytest.raises(ValueError, match="left.*right"):
        ChatStyle(local_align="middle")
