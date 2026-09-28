"""Tests for attachments: a message carries them, through every door.

What a message carries is not checked here — which links resolve, what is
kept and what is served is a backend's business. These only show that what a
peer attaches is what everyone receives.
"""

import pytest

from chatinho import (
    LOCAL,
    TOOL,
    Attachment,
    HookAnswer,
    HookExecute,
    HookListen,
    Reply,
    connector,
    require,
    tool,
)
from conftest import driven


def item(name: str) -> Attachment:
    return Attachment(name=name, media_type="text/html", data=b"<p>hi</p>")


def names(attachments) -> list:
    return [a.name for a in attachments]


@connector("ouvinte")
@require(HookListen)
class _Listener:
    def __init__(self) -> None:
        self.heard : list = []

    async def listen(self, msg) -> None:
        self.heard.append(msg)


@connector("relatorio")
@require(HookAnswer)
class _Reporter:
    async def answer(self, msg):
        return Reply("Here: [report](report.html)", (item("report.html"),))


@connector("lista")
@require(HookAnswer)
class _ListReporter:
    """Builds its Reply with a list, as a peer easily might."""

    async def answer(self, msg):
        return Reply("Here: [report](report.html)", [item("report.html")])   # type: ignore[arg-type]


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


@tool("simples", "answers with text only")
@require(HookExecute)
class _TextReply:
    async def execute(self, args="", by=LOCAL, **kwargs) -> Reply:
        return Reply("only text")


@tool("exporta", "exports")
@require(HookExecute)
class _Export:
    async def execute(self, args="", by=LOCAL, **kwargs):
        return Reply("[export](data.csv)", (item("data.csv"),))


def test_an_attachment_cannot_be_changed_after_it_is_made():
    with pytest.raises(AttributeError):
        item("a.html").name = "b.html"          # type: ignore[misc]


async def test_listeners_receive_what_was_attached():
    ear = _Listener()
    session, view = await driven(connectors=[ear])
    await view.say("See the [chart](revenue.html)", attachments=[item("revenue.html"), item("raw.csv")])
    await session.close()
    assert [names(m.attachments) for m in ear.heard] == [["revenue.html", "raw.csv"]]
    assert names(view.context()[-1].attachments) == ["revenue.html", "raw.csv"]


async def test_a_message_without_attachments_carries_none():
    session, view = await driven()
    await view.say("just words")
    await session.close()
    assert view.context()[-1].attachments == ()


async def test_ask_carries_attachments_to_the_peer_asked():
    session, view = await driven(connectors=[_Plain()])
    assert await view.ask(1, "Review [this](draft.md)", attachments=[item("draft.md")]) == "just text"
    await session.close()
    question = view.context()[0]
    assert (question.to, names(question.attachments)) == (1, ["draft.md"])


async def test_an_answer_can_attach_and_ask_still_returns_its_text():
    session, view = await driven(connectors=[_Reporter()])
    assert await view.ask(1, "report?") == "Here: [report](report.html)"
    await session.close()
    answer = view.context()[-1]
    assert (answer.frm, names(answer.attachments)) == (1, ["report.html"])


async def test_a_plain_string_answer_is_unchanged():
    session, view = await driven(connectors=[_Plain()])
    assert await view.ask(1, "?") == "just text"
    await session.close()
    question, answer = view.context()
    assert question.attachments == ()
    assert answer.attachments == ()


async def test_a_reply_built_with_a_list_is_carried_as_a_tuple():
    session, view = await driven(connectors=[_ListReporter()])
    await view.ask(1, "report?")
    await session.close()
    assert view.context()[-1].attachments == (item("report.html"),)


async def test_a_command_reply_without_attachments_carries_nothing():
    session, view = await driven(commands=[_TextReply()])
    assert await view.command("simples") == "only text"
    await session.close()
    assert [m.attachments for m in view.context()] == [(), ()]


async def test_a_command_that_returns_a_string_is_refused():
    session, view = await driven(commands=[_Text()])
    with pytest.raises(TypeError, match="must return a Reply"):
        await view.command("texto")
    await session.close()
    assert [m.text for m in view.context()] == ["/texto"]


async def test_a_command_result_can_attach_and_invoke_returns_its_text():
    session, view = await driven(commands=[_Export()])
    assert await view.command("exporta") == "[export](data.csv)"
    await session.close()
    invocation, result = view.context()
    assert invocation.attachments == ()
    assert (result.frm, names(result.attachments)) == (TOOL, ["data.csv"])
