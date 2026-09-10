"""Tests for ChatSession — the hub, driven without a terminal.

Everyone is a peer with an id, LOCAL is the user, and there are three
verbs. Every test here reaches the conversation the way the TUI does: through
a Driver that declared the hooks and was handed the capabilities at add_connector.
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import List, Optional

import pytest

from chatinho import (
    LOCAL,
    ChatMessage,
    ChatSession,
    TOOL,
    HookForget,
    HookLoad,
    Ask,
    HookAsk,
    HookAnswer,
    HookExecute,
    HookListen,
    HookSay,
    Say,
    backend,
    connector,
    require,
    tool,
)
from conftest import driven


@tool("eco", "repete")
@require(HookExecute)
class _Eco:
    async def execute(self, args="", by=LOCAL, **kwargs) -> str:
        return "eco: %s" % args


@connector("lento")
@require(HookAnswer)
class _Lento:
    async def answer(self, msg) -> str:
        await asyncio.sleep(0.3)
        return "finalmente"


@connector("rebenta")
@require(HookAnswer)
class _Rebenta:
    async def answer(self, msg):
        raise RuntimeError("kaboom")


@connector("rapido")
@require(HookAnswer)
class _Rapido:
    async def answer(self, msg) -> str:
        return "eco: %s" % msg.text


@connector("ouvinte")
@require(HookListen)
class _Ouvinte:
    def __init__(self) -> None:
        self.heard: list = []

    async def listen(self, msg) -> None:
        self.heard.append(msg.text)


@backend("memoria")
@require(HookListen)
@require(HookLoad)
@require(HookForget)
class _Archive:
    """An archive that keeps messages in a list, for tests that need a tier."""

    def __init__(self, seeded: Optional[List[ChatMessage]] = None) -> None:
        self.kept        : List[ChatMessage] = list(seeded or [])
        self.initialized : bool = False

    def initialize(self) -> None:
        self.initialized = True

    async def listen(self, msg) -> None:
        self.kept.append(msg)

    async def load(self, since=None, limit=None):
        kept = self.kept
        if since is not None:
            kept = [m for m in kept if m.timestamp >= since]
        return kept[-limit:] if limit else list(kept)

    async def forget(self, before=None) -> int:
        dropped = len(self.kept) if before is None else len([m for m in self.kept
                                                             if m.timestamp < before])
        self.kept = [] if before is None else [m for m in self.kept if m.timestamp >= before]
        return dropped


# === Ids and names ==============================================================


async def test_the_user_is_peer_zero_and_connectors_are_numbered():
    """Commands are not among them: they have no id at all."""
    session, view = await driven(connectors=[_Lento(), _Rapido()], commands=[_Eco()])
    assert view.peer_id == LOCAL
    assert sorted(view.peers()) == [0, 1, 2]
    assert session.id_of("lento") == 1
    assert session.id_of("rapido") == 2
    assert session.id_of("eco") is None, "a command must not be addressable"
    assert list(session.commands) == ["eco"]
    await session.close()


async def test_a_taken_id_is_refused():
    session, _ = await driven()
    with pytest.raises(ValueError, match="already taken"):
        session.add_connector(_Eco(), at=LOCAL)
    await session.close()


async def test_renaming_does_not_change_the_address():
    """The id routes; the name is only what the chat shows."""
    session, view = await driven(connectors=[_Rapido()])
    peer = view.peers()[1]
    peer.name = "outro-nome"
    assert await view.ask(1, "ola") == "eco: ola"
    assert session.id_of("outro-nome") == 1
    await session.close()


# === say ========================================================================


async def test_a_say_reaches_everyone_but_the_speaker():
    ouvinte = _Ouvinte()
    session, view = await driven(connectors=[ouvinte])
    await view.say("bom dia")
    await asyncio.sleep(0.02)
    assert ouvinte.heard == ["bom dia"]
    assert view.heard == []            # the speaker does not hear itself
    await session.close()


async def test_a_reply_to_a_say_is_another_say():
    session, view = await driven(connectors=[_Ouvinte()])
    first = await view.say("uma pergunta ao ar")
    await view.say("uma resposta", reply_to=first)
    assert [m.reply_to for m in view.context()] == [None, first]
    await session.close()


# === ask / answer ===============================================================


async def test_ask_returns_the_answer():
    session, view = await driven(connectors=[_Rapido()])
    assert await view.ask(1, "ola") == "eco: ola"
    await session.close()


async def test_running_a_command_answers_the_peer_that_ran_it():
    """The answer goes back to whoever ran it, and the whole of it is recorded.

    A command is still not a peer — it has no id and no queue — but there is
    one conversation, so the invocation and what it answered cross the session
    like anything else. The invocation is *addressed* to TOOL rather than said
    to the room, which is what keeps a peer from answering somebody else's
    command.
    """
    session, view = await driven(commands=[_Eco()])
    assert await view.command("eco", "ola") == "eco: ola"
    invocacao, resposta = view.context()
    assert (invocacao.text, invocacao.frm, invocacao.to) == ("/eco ola", LOCAL, TOOL)
    assert (resposta.text, resposta.frm, resposta.to) == ("eco: ola", TOOL, None)
    assert resposta.reply_to == invocacao.id
    await session.close()


async def test_running_a_command_that_does_not_exist_answers_nothing():
    session, view = await driven()
    assert await view.command("nao-existe") is None
    await session.close()


async def test_a_command_that_says_writes_and_still_answers():
    @tool("relata", "escreve enquanto trabalha")
    @require(HookExecute)
    @require(HookSay)
    class Relata:
        say : Say

        async def execute(self, args="", by=LOCAL, **kwargs) -> str:
            await self.say("a trabalhar…")
            return "pronto"

    session, view = await driven(commands=[Relata()])
    assert await view.command("relata") == "pronto"
    assert view.texts() == ["/relata", "a trabalhar…", "pronto"]
    await session.close()


async def test_a_command_is_told_which_peer_ran_it():
    seen: list = []

    @tool("quem", "")
    @require(HookExecute)
    class Quem:
        async def execute(self, args="", by=LOCAL, **kwargs) -> str:
            seen.append(by)
            return "ok"

    session, view = await driven(commands=[Quem()])
    await view.command("quem")
    assert seen == [LOCAL]
    await session.close()


async def test_registering_something_that_cannot_execute_is_refused():
    class NotACommand:
        name = "nope"

    session, _ = await driven()
    with pytest.raises(TypeError, match="HookExecute"):
        session.add_command(NotACommand())
    await session.close()


async def test_asking_an_unknown_id_raises():
    session, view = await driven()
    with pytest.raises(ValueError, match="No peer with id"):
        await view.ask(99, "ola")
    await session.close()


async def test_a_slow_peer_holds_up_only_itself():
    """Each peer has its own queue: one second is not two."""
    session, view = await driven(connectors=[_Lento(), _Rapido()])
    started = time.perf_counter()
    slow, quick = await asyncio.gather(view.ask(1, "?"), view.ask(2, "ola"))
    elapsed = time.perf_counter() - started
    assert (slow, quick) == ("finalmente", "eco: ola")
    assert elapsed < 0.45, "as duas perguntas serializaram: %.2fs" % elapsed
    await session.close()


async def test_a_peer_that_raises_does_not_take_the_chat_down():
    session, view = await driven(connectors=[_Rebenta(), _Rapido()])
    asyncio.create_task(view.ask(1, "?"))       # never answers
    await asyncio.sleep(0.05)
    assert await view.ask(2, "ola") == "eco: ola"
    await session.close()


async def test_a_peer_can_ask_the_user():
    """ask(LOCAL, ...) is what the old inbox was, with no extra concept."""
    session, view = await driven(commands=[_Eco()])
    view.answers.append("sim, autorizo")

    @connector("agente")
    @require(HookAsk)
    class Agente:
        ask: Ask

    agente = Agente()
    session.add_connector(agente)
    await session.start()
    assert await agente.ask(LOCAL, "Autorizas?") == "sim, autorizo"
    assert [m.text for m in view.asked] == ["Autorizas?"]
    await session.close()


async def test_an_answer_given_later_still_resolves_the_ask():
    """answer may return None; what is said later with reply_to resolves the ask.

    There is no separate grant for answering late. A peer that cannot answer
    inline — a terminal waiting on a person, a connector waiting on a server —
    returns None and says the answer when it has it, and the session matches it
    by ``reply_to``. That is the same door as any other say.
    """

    @connector("adiado")
    @require(HookAnswer)
    @require(HookSay)
    class Adiado:
        say : Say

        def __init__(self) -> None:
            self.pendente = None

        async def answer(self, msg):
            self.pendente = msg
            return None

    session, view = await driven()
    adiado = Adiado()
    at = session.add_connector(adiado)
    await session.start()

    pergunta = asyncio.create_task(view.ask(at, "e depois?"))
    await asyncio.sleep(0.02)
    await adiado.say("agora sim", reply_to=adiado.pendente.id)
    assert await pergunta == "agora sim"
    await session.close()


# === Grants =====================================================================


async def test_a_peer_gets_only_what_it_declared():
    @connector("mudo")
    @require(HookSay)
    class Mudo:
        say: Say

    session, _ = await driven()
    mudo = Mudo()
    session.add_connector(mudo)
    assert hasattr(mudo, "say")
    assert not hasattr(mudo, "ask")
    assert not hasattr(mudo, "context")
    await session.close()


async def test_nobody_can_speak_in_another_name():
    """frm is bound at add_connector, not passed as an argument."""
    session, view = await driven(connectors=[_Ouvinte()])
    await view.say("sou eu")
    assert view.context()[0].frm == LOCAL
    await session.close()


# === History ====================================================================


async def test_context_narrows_by_index_and_by_time():
    session, view = await driven()
    for n in range(5):
        await view.say("m%d" % n)
    assert [m.text for m in view.context(limit=2)] == ["m3", "m4"]
    assert [m.text for m in view.context(start=3)] == ["m3", "m4"]
    cut = view.context()[3].timestamp
    assert [m.text for m in view.context(since=cut)] == ["m3", "m4"]
    assert view.context(limit=0) == []
    await session.close()


async def test_context_returns_a_copy():
    session, view = await driven()
    await view.say("guardada")
    view.context().clear()
    assert view.texts() == ["guardada"]
    await session.close()


# === The older tier =============================================================


async def test_what_is_said_reaches_the_one_that_listens():
    """Listening runs on the listener's own queue, and close() drains it.

    Asserting straight after ``say`` would be asserting on timing; asserting
    after ``close`` is the guarantee that matters — nothing said is lost.
    """
    store = _Archive()
    session, view = await driven(backend=store)
    assert store.initialized is True
    await view.say("guarda isto")
    await session.close()
    assert [m.text for m in store.kept] == ["guarda isto"]


async def test_context_spans_both_tiers_without_saying_which():
    """The whole point of one interface: the caller cannot tell them apart."""
    older = ChatMessage(id="old-1", text="de ontem", frm=LOCAL,
                        timestamp=datetime.now() - timedelta(days=1))
    session, view = await driven(backend=_Archive([older]))
    await view.say("de hoje")
    assert [m.text for m in view.context()] == ["de ontem", "de hoje"]
    await session.close()


async def test_recall_is_bounded_and_the_bound_is_the_session_s():
    older = [ChatMessage(id="old-%d" % n, text="m%d" % n, frm=LOCAL,
                         timestamp=datetime.now() - timedelta(minutes=5 - n))
             for n in range(5)]
    session, view = await driven(backend=_Archive(older), recall=2)
    assert [m.text for m in view.context()] == ["m3", "m4"]
    await session.close()


async def test_a_backend_that_only_listens_is_not_an_error():
    """Declaring less means doing less, not failing."""

    @backend("so-escreve")
    @require(HookListen)
    class WriteOnly:
        def __init__(self) -> None:
            self.kept: list = []

        async def listen(self, msg) -> None:
            self.kept.append(msg)

    store = WriteOnly()
    session, view = await driven(backend=store)
    await view.say("ainda assim guardada")
    assert [m.text for m in view.context()] == ["ainda assim guardada"]
    await session.close()
    assert [m.text for m in store.kept] == ["ainda assim guardada"]


async def test_a_listener_that_fails_does_not_lose_the_message():
    @backend("avariado")
    @require(HookListen)
    class Broken:
        async def listen(self, msg) -> None:
            raise RuntimeError("disco cheio")

    session, view = await driven(backend=Broken())
    await view.say("continua na conversa")
    assert [m.text for m in view.context()] == ["continua na conversa"]
    await session.close()


async def test_forget_without_a_backend_drops_nothing():
    session, _ = await driven()
    assert await session.forget() == 0
    await session.close()


async def test_forget_reaches_the_one_that_holds():
    store = _Archive()
    session, view = await driven(backend=store)
    await view.say("efémera")
    await asyncio.sleep(0.02)          # let its queue run
    assert await session.forget() == 1
    assert store.kept == []
    await session.close()




# === The id a class declares ====================================================


async def test_a_connector_can_pin_the_id_it_answers_to():
    """Being peer zero is what the terminal *is*, not a favour at add_connector.

    @connector(name, id=…) is for a connector that can only be one peer. The
    session numbers everything else from one, in attachment order.
    """

    @connector("terminal", id=LOCAL)
    @require(HookListen)
    class Terminal:
        async def listen(self, msg) -> None:
            pass

    session = ChatSession(connectors=[Terminal(), _Rapido()])
    assert session.id_of("terminal") == LOCAL
    assert session.id_of("rapido") == 1
    await session.close()


def test_the_caller_may_still_pin_a_different_id():
    @connector("teimoso", id=LOCAL)
    @require(HookListen)
    class Teimoso:
        async def listen(self, msg) -> None:
            pass

    session = ChatSession()
    assert session.add_connector(Teimoso(), at=7) == 7


def test_a_declared_id_may_not_be_TOOL_or_anything_but_an_int():
    with pytest.raises(ValueError, match="TOOL"):
        @connector("ladrao", id=TOOL)
        class Ladrao:
            pass

    with pytest.raises(ValueError, match="int"):
        @connector("torto", id="zero")
        class Torto:
            pass


# === run(), and what serves ======================================================


async def test_the_first_peer_to_finish_serving_ends_the_chat():
    """serve() is lifecycle, not a hook: it runs until it is finished.

    Quitting the terminal is the end of the chat even when a server is still
    listening, so the session waits for the first and cancels the rest.
    """
    cancelled = []

    @connector("curto")
    @require(HookSay)
    class Curto:
        say : Say
        async def serve(self) -> None:
            await self.say("e pronto")

    @connector("longo")
    @require(HookListen)
    class Longo:
        async def listen(self, msg) -> None:
            pass
        async def serve(self) -> None:
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled.append(True)
                raise

    session = ChatSession(connectors=[Curto(), Longo()])
    await asyncio.wait_for(session._serve(), timeout=2)
    assert cancelled == [True], "the one still serving should have been cancelled"
    assert [m.text for m in session._context()] == ["e pronto"]


async def test_a_session_with_nothing_serving_runs_until_it_is_stopped():
    """A bot has no terminal to quit: it runs until something interrupts it."""
    session = ChatSession(connectors=[_Rapido()])
    running = asyncio.create_task(session._serve())
    await asyncio.sleep(0.05)
    assert not running.done()

    running.cancel()
    with pytest.raises(asyncio.CancelledError):
        await running


async def test_a_peer_that_fails_while_serving_is_not_swallowed():
    @connector("avariado")
    @require(HookListen)
    class Avariado:
        async def listen(self, msg) -> None:
            pass
        async def serve(self) -> None:
            raise RuntimeError("o servidor caiu")

    session = ChatSession(connectors=[Avariado()])
    with pytest.raises(RuntimeError, match="caiu"):
        await session._serve()


async def test_an_async_initialize_is_awaited_by_start():
    """initialize() runs from start(), where a loop exists — so it may be async.

    It used to run synchronously at add_connector(), before there was
    necessarily a loop to await one; now that it runs from start(), that
    restriction is gone.
    """

    @connector("tarde")
    @require(HookListen)
    class Tarde:
        def __init__(self) -> None:
            self.initialized = False

        async def initialize(self) -> None:
            self.initialized = True

        async def listen(self, msg) -> None:
            pass

    tarde = Tarde()
    session = ChatSession(connectors=[tarde])
    assert tarde.initialized is False
    await session.start()
    assert tarde.initialized is True
    await session.close()
