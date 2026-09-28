"""Tests for attachments: they go to the backend, and the message stays text.

A peer attaches through every door it speaks through; the session hands what
it attached to whoever declared ``HookKeep``, under the new message's id,
before anyone hears the message. Opening one is ``locate``, which the session
routes to whoever declared ``HookLink``.
"""

import logging
from typing import Dict, List, Optional, Tuple

import pytest

from chatinho import (
    LOCAL,
    TOOL,
    Attachment,
    HookAnswer,
    HookExecute,
    HookKeep,
    HookLink,
    HookListen,
    HookLocate,
    Locate,
    Reply,
    backend,
    connector,
    require,
    tool,
)
from conftest import driven


def item(name: str) -> Attachment:
    return Attachment(name=name, media_type="text/html", data=b"<p>hi</p>")


@backend("guarda")
@require(HookKeep)
@require(HookLink)
class _Keeper:
    """Keeps attachments in a dict and links them as ``mem://<id>/<name>``."""

    def __init__(self) -> None:
        self.kept : Dict[Tuple[str, str], Attachment] = {}

    async def keep(self, msg_id: str, attachments) -> None:
        for attached in attachments:
            self.kept[(msg_id, attached.name)] = attached

    async def link(self, msg_id: str, name: str) -> Optional[str]:
        return "mem://%s/%s" % (msg_id, name) if (msg_id, name) in self.kept else None


@backend("partido")
@require(HookKeep)
@require(HookLink)
class _Broken:
    async def keep(self, msg_id, attachments) -> None:
        raise RuntimeError("disk full")

    async def link(self, msg_id, name) -> Optional[str]:
        raise RuntimeError("disk gone")


@connector("ouvinte")
@require(HookListen)
class _Listener:
    """Records what it heard, and what the keeper already had when it heard it."""

    def __init__(self, keeper: Optional[_Keeper] = None) -> None:
        self.keeper = keeper
        self.heard  : list = []
        self.seen   : List[List[Tuple[str, str]]] = []

    async def listen(self, msg) -> None:
        self.heard.append(msg)
        if self.keeper is not None:
            self.seen.append([k for k in self.keeper.kept if k[0] == msg.id])


@connector("olheiro")
@require(HookLocate)
class _Looker:
    locate : Locate


@connector("relatorio")
@require(HookAnswer)
class _Reporter:
    async def answer(self, msg):
        return Reply("Here: [report](report.html)", (item("report.html"),))


@connector("simples")
@require(HookAnswer)
class _Plain:
    async def answer(self, msg) -> str:
        return "just text"


@tool("texto", "answers with a plain string")
@require(HookExecute)
class _Text:
    async def execute(self, args="", by=LOCAL, **kwargs):
        return "only text"


@tool("exporta", "exports")
@require(HookExecute)
class _Export:
    async def execute(self, args="", by=LOCAL, **kwargs):
        return Reply("[export](data.csv)", (item("data.csv"),))


def test_an_attachment_cannot_be_changed_after_it_is_made():
    with pytest.raises(AttributeError):
        item("a.html").name = "b.html"          # type: ignore[misc]


def test_a_message_has_no_attachments_field():
    from chatinho import ChatMessage

    assert not hasattr(ChatMessage(id="msg-1", text="hi"), "attachments")


# === Keeping ========================================================================

async def test_attachments_are_kept_before_anyone_hears_the_message():
    keeper = _Keeper()
    ear    = _Listener(keeper)
    session, view = await driven(connectors=[ear], backend=keeper)
    msg_id = await view.say("See the [chart](revenue.html)", attachments=[item("revenue.html")])
    await session.close()
    assert keeper.kept[(msg_id, "revenue.html")] == item("revenue.html")
    assert ear.seen == [[(msg_id, "revenue.html")]]


async def test_listeners_and_context_get_text_only():
    keeper = _Keeper()
    ear    = _Listener()
    session, view = await driven(connectors=[ear], backend=keeper)
    await view.say("See the [chart](revenue.html)", attachments=[item("revenue.html")])
    await session.close()
    assert [m.text for m in ear.heard] == ["See the [chart](revenue.html)"]
    assert not any(hasattr(m, "attachments") for m in ear.heard + view.context())


async def test_without_a_keeper_the_text_is_posted_and_attachments_dropped():
    session, view = await driven()
    await view.say("See the [chart](revenue.html)", attachments=[item("revenue.html")])
    await session.close()
    assert view.texts() == ["See the [chart](revenue.html)"]


async def test_a_keeper_that_fails_is_logged_and_the_text_still_posted(caplog):
    session, view = await driven(backend=_Broken())
    with caplog.at_level(logging.ERROR):
        await view.say("See the [chart](revenue.html)", attachments=[item("revenue.html")])
    await session.close()
    assert view.texts() == ["See the [chart](revenue.html)"]
    assert "Keeping the attachments" in caplog.text


async def test_ask_keeps_under_the_question():
    keeper = _Keeper()
    session, view = await driven(connectors=[_Plain()], backend=keeper)
    assert await view.ask(1, "Review [this](draft.md)", attachments=[item("draft.md")]) == "just text"
    await session.close()
    question = view.context()[0]
    assert set(keeper.kept) == {(question.id, "draft.md")}


async def test_an_answer_keeps_under_the_answer_and_ask_returns_its_text():
    keeper = _Keeper()
    session, view = await driven(connectors=[_Reporter()], backend=keeper)
    assert await view.ask(1, "report?") == "Here: [report](report.html)"
    await session.close()
    answer = view.context()[-1]
    assert (answer.frm, set(keeper.kept)) == (1, {(answer.id, "report.html")})


async def test_a_plain_string_answer_keeps_nothing():
    keeper = _Keeper()
    session, view = await driven(connectors=[_Plain()], backend=keeper)
    assert await view.ask(1, "?") == "just text"
    await session.close()
    assert keeper.kept == {}


async def test_a_command_result_keeps_under_the_result_not_the_invocation():
    keeper = _Keeper()
    session, view = await driven(commands=[_Export()], backend=keeper)
    assert await view.command("exporta") == "[export](data.csv)"
    await session.close()
    invocation, result = view.context()
    assert (result.frm, set(keeper.kept)) == (TOOL, {(result.id, "data.csv")})
    assert all(key[0] != invocation.id for key in keeper.kept)


async def test_a_reply_built_with_a_list_is_kept_as_given():
    keeper = _Keeper()

    @connector("lista")
    @require(HookAnswer)
    class _ListReporter:
        async def answer(self, msg):
            return Reply("Here: [report](report.html)", [item("report.html")])   # type: ignore[arg-type]

    session, view = await driven(connectors=[_ListReporter()], backend=keeper)
    await view.ask(1, "report?")
    await session.close()
    assert list(keeper.kept.values()) == [item("report.html")]


async def test_a_command_that_returns_a_string_is_refused():
    session, view = await driven(commands=[_Text()])
    with pytest.raises(TypeError, match="must return a Reply"):
        await view.command("texto")
    await session.close()
    assert view.texts() == ["/texto"]


# === Locating =======================================================================

async def test_a_peer_locates_through_the_backend():
    keeper = _Keeper()
    looker = _Looker()
    session, view = await driven(connectors=[looker], backend=keeper)
    msg_id = await view.say("See the [chart](revenue.html)", attachments=[item("revenue.html")])
    assert await looker.locate(msg_id, "revenue.html") == "mem://%s/revenue.html" % msg_id
    assert await looker.locate(msg_id, "other.html") is None
    await session.close()


async def test_without_a_linking_backend_locate_is_none():
    looker = _Looker()
    session, view = await driven(connectors=[looker])
    msg_id = await view.say("See the [chart](revenue.html)", attachments=[item("revenue.html")])
    assert await looker.locate(msg_id, "revenue.html") is None
    await session.close()


async def test_a_backend_that_fails_to_link_is_logged_and_none(caplog):
    session, view = await driven(backend=_Broken())
    with caplog.at_level(logging.ERROR):
        assert await session.locate("msg-1", "revenue.html") is None
    await session.close()
    assert "Linking revenue.html of msg-1 failed" in caplog.text
