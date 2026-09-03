"""Tests for ChatSession — the hub, driven without a terminal.

Everyone is a participant with an id, LOCAL is the user, and there are three
verbs. Every test here reaches the conversation the way the TUI does: through
a Driver that declared the hooks and was handed the capabilities at attach.
"""

import asyncio
import time

import pytest

from chatinho import (
    LOCAL,
    Answer,
    Ask,
    HookAsk,
    HookOnAsk,
    HookOnSay,
    HookSay,
    Say,
    backend,
    connector,
    require,
    tool,
)
from conftest import driven


@tool("eco", "repete")
@require(HookOnAsk)
class _Eco:
    async def on_ask(self, msg) -> str:
        return "eco: %s" % msg.text


@tool("lento", "demora a responder")
@require(HookOnAsk)
class _Lento:
    async def on_ask(self, msg) -> str:
        await asyncio.sleep(0.3)
        return "finalmente"


@tool("rebenta", "falha sempre")
@require(HookOnAsk)
class _Rebenta:
    async def on_ask(self, msg):
        raise RuntimeError("kaboom")


@connector("ouvinte")
@require(HookOnSay)
class _Ouvinte:
    def __init__(self) -> None:
        self.heard: list = []

    async def on_say(self, msg) -> None:
        self.heard.append(msg.text)


@backend("memoria")
@require(__import__("chatinho").HookSave)
@require(__import__("chatinho").HookLoad)
@require(__import__("chatinho").HookDelete)
class _Backend:
    def __init__(self) -> None:
        self.data: dict = {}
        self.initialized = False

    def initialize(self) -> None:
        self.initialized = True

    def save(self, key, data) -> bool:
        self.data[key] = data
        return True

    def load(self, key):
        return self.data.get(key)

    def delete(self, key) -> bool:
        return self.data.pop(key, None) is not None


# === Ids and names ==============================================================


async def test_the_user_is_participant_zero_and_the_rest_are_numbered():
    session, view = await driven(participants=[_Eco(), _Lento()])
    assert view.chat_id == LOCAL
    assert sorted(view.participants()) == [0, 1, 2]
    assert session.id_of("eco") == 1
    assert session.id_of("lento") == 2
    assert session.id_of("nao-existe") is None
    await session.close()


async def test_a_taken_id_is_refused():
    session, _ = await driven()
    with pytest.raises(ValueError, match="already taken"):
        session.attach(_Eco(), at=LOCAL)
    await session.close()


async def test_renaming_does_not_change_the_address():
    """The id routes; the name is only what the chat shows."""
    session, view = await driven(participants=[_Eco()])
    eco = view.participants()[1]
    eco.name = "outro-nome"
    assert await view.ask(1, "ola") == "eco: ola"
    assert session.id_of("outro-nome") == 1
    await session.close()


# === say ========================================================================


async def test_a_say_reaches_everyone_but_the_speaker():
    ouvinte = _Ouvinte()
    session, view = await driven(participants=[ouvinte])
    await view.say("bom dia")
    await asyncio.sleep(0.02)
    assert ouvinte.heard == ["bom dia"]
    assert view.heard == []            # the speaker does not hear itself
    await session.close()


async def test_a_reply_to_a_say_is_another_say():
    session, view = await driven(participants=[_Ouvinte()])
    first = await view.say("uma pergunta ao ar")
    await view.say("uma resposta", reply_to=first)
    assert [m.reply_to for m in view.load_messages()] == [None, first]
    await session.close()


# === ask / answer ===============================================================


async def test_ask_returns_the_answer():
    session, view = await driven(participants=[_Eco()])
    assert await view.ask(1, "ola") == "eco: ola"
    await session.close()


async def test_a_command_is_an_ask_to_a_tool():
    session, view = await driven(participants=[_Eco()])
    assert await view.command("eco", "ola") == "eco: ola"
    history = view.load_messages()
    assert (history[0].frm, history[0].to) == (LOCAL, 1)
    assert (history[1].frm, history[1].to) == (1, LOCAL)
    assert history[1].reply_to == history[0].id
    await session.close()


async def test_asking_an_unknown_id_raises():
    session, view = await driven()
    with pytest.raises(ValueError, match="No participant with id"):
        await view.ask(99, "ola")
    await session.close()


async def test_a_slow_participant_holds_up_only_itself():
    """Each participant has its own queue: one second is not two."""
    session, view = await driven(participants=[_Lento(), _Eco()])
    started = time.perf_counter()
    slow, quick = await asyncio.gather(view.ask(1, "?"), view.ask(2, "ola"))
    elapsed = time.perf_counter() - started
    assert (slow, quick) == ("finalmente", "eco: ola")
    assert elapsed < 0.45, "as duas perguntas serializaram: %.2fs" % elapsed
    await session.close()


async def test_a_participant_that_raises_does_not_take_the_chat_down():
    session, view = await driven(participants=[_Rebenta(), _Eco()])
    asyncio.create_task(view.ask(1, "?"))       # never answers
    await asyncio.sleep(0.05)
    assert await view.ask(2, "ola") == "eco: ola"
    await session.close()


async def test_a_participant_can_ask_the_user():
    """ask(LOCAL, ...) is what the old inbox was, with no extra concept."""
    session, view = await driven(participants=[_Eco()])
    view.answers.append("sim, autorizo")

    @connector("agente")
    @require(HookAsk)
    class Agente:
        ask: Ask

    agente = Agente()
    session.attach(agente)
    await session.start()
    assert await agente.ask(LOCAL, "Autorizas?") == "sim, autorizo"
    assert [m.text for m in view.asked] == ["Autorizas?"]
    await session.close()


async def test_an_answer_given_later_still_resolves_the_ask():
    """on_ask may return None and answer once it knows."""

    @connector("adiado")
    @require(HookOnAsk)
    class Adiado:
        answer: Answer

        def __init__(self) -> None:
            self.pendente = None

        async def on_ask(self, msg):
            self.pendente = msg
            return None

    session, view = await driven()
    adiado = Adiado()
    at = session.attach(adiado)
    await session.start()

    pergunta = asyncio.create_task(view.ask(at, "e depois?"))
    await asyncio.sleep(0.02)
    await adiado.answer(adiado.pendente, "agora sim")
    assert await pergunta == "agora sim"
    await session.close()


# === Grants =====================================================================


async def test_a_participant_gets_only_what_it_declared():
    @connector("mudo")
    @require(HookSay)
    class Mudo:
        say: Say

    session, _ = await driven()
    mudo = Mudo()
    session.attach(mudo)
    assert hasattr(mudo, "say")
    assert not hasattr(mudo, "ask")
    assert not hasattr(mudo, "load_messages")
    await session.close()


async def test_nobody_can_speak_in_another_name():
    """frm is bound at attach, not passed as an argument."""
    session, view = await driven(participants=[_Ouvinte()])
    await view.say("sou eu")
    assert view.load_messages()[0].frm == LOCAL
    await session.close()


# === History ====================================================================


async def test_load_messages_narrows_by_index_and_by_time():
    session, view = await driven()
    for n in range(5):
        await view.say("m%d" % n)
    assert [m.text for m in view.load_messages(limit=2)] == ["m3", "m4"]
    assert [m.text for m in view.load_messages(start=3)] == ["m3", "m4"]
    cut = view.load_messages()[3].timestamp
    assert [m.text for m in view.load_messages(since=cut)] == ["m3", "m4"]
    assert view.load_messages(limit=0) == []
    await session.close()


async def test_load_messages_returns_a_copy():
    session, view = await driven()
    await view.say("guardada")
    view.load_messages().clear()
    assert view.texts() == ["guardada"]
    await session.close()


# === Persistence ================================================================


async def test_backend_round_trip():
    store = _Backend()
    session, _ = await driven(backend=store)
    assert store.initialized is True
    assert session.save_data("k", {"a": 1}) is True
    assert session.load_data("k") == {"a": 1}
    assert session.delete_data("k") is True
    assert session.load_data("k") is None
    await session.close()


async def test_persistence_without_a_backend_raises():
    session, _ = await driven()
    for call in (lambda: session.save_data("k", 1),
                 lambda: session.load_data("k"),
                 lambda: session.delete_data("k")):
        with pytest.raises(RuntimeError, match="No backend"):
            call()
    await session.close()


async def test_the_backend_must_declare_what_the_session_asks_of_it():
    """A capability the backend never had must fail loudly, not silently."""

    @backend("so-leitura")
    @require(__import__("chatinho").HookLoad)
    class ReadOnly:
        def load(self, key):
            return None

    session, _ = await driven(backend=ReadOnly())
    with pytest.raises(RuntimeError, match="does not declare HookSave"):
        session.save_data("k", 1)
    await session.close()


# === Lifecycle ==================================================================


async def test_close_shuts_every_participant_down():
    calls: list = []

    @connector("com-servidor")
    @require(HookOnSay)
    class ComServidor:
        async def on_say(self, msg) -> None:
            pass

        def shutdown(self) -> None:
            calls.append("desligado")

    session, _ = await driven(participants=[ComServidor()])
    await session.close()
    assert calls == ["desligado"]


async def test_one_failing_shutdown_does_not_block_the_others():
    calls: list = []

    @connector("mau")
    @require(HookOnSay)
    class Mau:
        async def on_say(self, msg) -> None:
            pass

        def shutdown(self) -> None:
            raise RuntimeError("nao desligo")

    @connector("bom")
    @require(HookOnSay)
    class Bom:
        async def on_say(self, msg) -> None:
            pass

        def shutdown(self) -> None:
            calls.append("bom")

    session, _ = await driven(participants=[Mau(), Bom()])
    await session.close()
    assert calls == ["bom"]
