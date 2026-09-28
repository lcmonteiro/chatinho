"""Tests for the attachment rule: only what the text links to travels.

The rule lives in chat_message and imports nothing but the standard library,
so most of these need no session and no terminal; the last ones go through a
session, the way a peer would.
"""

import asyncio

import pytest

from chatinho import (
    LOCAL,
    TOOL,
    Attachment,
    ChatMessage,
    HookAnswer,
    HookExecute,
    HookListen,
    Reply,
    connector,
    require,
    tool,
)
from chatinho.chat_message import attached, attachment_url
from conftest import driven


def item(name: str) -> Attachment:
    return Attachment(name=name, media_type="text/html", data=b"<p>hi</p>")


def names(attachments) -> list:
    return [a.name for a in attachments]


# === Which attachments travel ======================================================

def test_a_linked_attachment_is_kept():
    assert names(attached("See the [chart](revenue.html)", [item("revenue.html")])) == ["revenue.html"]


def test_an_image_link_with_a_dot_slash_is_kept():
    assert names(attached("![plot](./plot.png)", [item("plot.png")])) == ["plot.png"]


def test_an_unlinked_attachment_is_dropped():
    kept = attached("See the [chart](revenue.html)", [item("revenue.html"), item("raw.csv")])
    assert names(kept) == ["revenue.html"]


def test_order_is_the_order_given_not_the_order_linked():
    kept = attached("[b](b.html) and [a](a.html)", [item("a.html"), item("b.html")])
    assert names(kept) == ["a.html", "b.html"]


def test_no_attachments_and_no_links_is_nothing():
    assert attached("just words", []) == ()


def test_an_angle_bracket_target_and_a_title():
    kept = attached('[r](<my report.html> "Report")', [item("my report.html")])
    assert names(kept) == ["my report.html"]


def test_a_percent_encoded_target_matches_the_plain_name():
    assert names(attached("[r](my%20report.html)", [item("my report.html")])) == ["my report.html"]


@pytest.mark.parametrize("link", [
    "[x](https://example.com/a.html)",
    "[x](mailto:someone@example.com)",
    "[x](//example.com/a.html)",
    "[x](/absolute.html)",
    "[x](#top)",
    "[x](page.html?raw=1)",
])
def test_absolute_fragment_and_query_targets_are_not_attachment_links(link):
    assert attached(link, []) == ()


def test_a_link_in_a_code_span_is_not_a_link():
    assert attached("write `[x](code.html)` to link", []) == ()


def test_a_link_in_a_fenced_block_is_not_a_link():
    text = "Like this:\n```markdown\n[x](fence.html)\n```\nand [real](real.html)"
    assert names(attached(text, [item("real.html")])) == ["real.html"]


def test_a_link_in_an_unclosed_fence_is_not_a_link():
    assert attached("~~~\n[x](fence.html)\n", []) == ()


# === What is rejected ==============================================================

def test_a_link_to_a_missing_attachment_raises_and_names_it():
    with pytest.raises(ValueError, match="revenue.html"):
        attached("See the [chart](revenue.html)", [])


@pytest.mark.parametrize("name", ["", ".", "..", "../secret.txt", "a/b.html", "a\\b.html"])
def test_a_name_that_is_not_one_segment_raises(name):
    with pytest.raises(ValueError, match="one relative path segment"):
        attached("", [item(name)])


def test_two_attachments_with_one_name_raise():
    with pytest.raises(ValueError, match="chart.html"):
        attached("[c](chart.html)", [item("chart.html"), item("chart.html")])


def test_an_attachment_cannot_be_changed_after_it_is_made():
    with pytest.raises(AttributeError):
        item("a.html").name = "b.html"          # type: ignore[misc]


# === Where a link points ===========================================================

def message_with(*attachment_names: str) -> ChatMessage:
    return ChatMessage(id="msg-42", text="", attachments=tuple(item(n) for n in attachment_names))


def test_an_attachment_link_resolves_under_its_message():
    url = attachment_url("http://localhost:8765", message_with("revenue.html"), "revenue.html")
    assert url == "http://localhost:8765/m/msg-42/revenue.html"


def test_a_trailing_slash_on_the_base_is_not_doubled():
    url = attachment_url("http://localhost:8765/", message_with("revenue.html"), "./revenue.html")
    assert url == "http://localhost:8765/m/msg-42/revenue.html"


def test_a_name_that_needs_quoting_is_quoted():
    url = attachment_url("http://h", message_with("my report.html"), "my%20report.html")
    assert url == "http://h/m/msg-42/my%20report.html"


def test_no_base_means_no_url():
    assert attachment_url(None, message_with("revenue.html"), "revenue.html") is None


def test_a_link_to_something_the_message_does_not_carry_has_no_url():
    assert attachment_url("http://h", message_with("revenue.html"), "other.html") is None


def test_an_absolute_link_is_not_an_attachment_url():
    assert attachment_url("http://h", message_with("revenue.html"), "https://example.com") is None


# === Through the session: every door attaches ======================================


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
        return Reply("Here: [report](report.html)", (item("report.html"), item("unused.html")))


@connector("esquecido")
@require(HookAnswer)
class _Forgetful:
    async def answer(self, msg):
        return Reply("Here: [report](report.html)")


@connector("simples")
@require(HookAnswer)
class _Plain:
    async def answer(self, msg) -> str:
        return "just text"


@tool("exporta", "exports")
@require(HookExecute)
class _Export:
    async def execute(self, args="", by=LOCAL, **kwargs):
        return Reply("[export](data.csv)", (item("data.csv"),))


@tool("quebrado", "links to nothing")
@require(HookExecute)
class _Broken:
    async def execute(self, args="", by=LOCAL, **kwargs):
        return Reply("[export](data.csv)")


async def test_listeners_receive_only_the_linked_attachments():
    ear = _Listener()
    session, view = await driven(connectors=[ear])
    await view.say("See the [chart](revenue.html)", attachments=[item("revenue.html"), item("raw.csv")])
    await session.close()
    assert [names(m.attachments) for m in ear.heard] == [["revenue.html"]]
    assert names(view.context()[-1].attachments) == ["revenue.html"]


async def test_say_with_a_missing_target_raises_and_posts_nothing():
    session, view = await driven()
    with pytest.raises(ValueError, match="revenue.html"):
        await view.say("See the [chart](revenue.html)")
    await session.close()
    assert view.context() == []


async def test_a_rejected_message_uses_up_no_id():
    session, view = await driven()
    with pytest.raises(ValueError):
        await view.say("[chart](revenue.html)")
    assert await view.say("hello") == "msg-1"
    await session.close()


async def test_ask_carries_attachments_to_the_peer_asked():
    session, view = await driven(connectors=[_Plain()])
    assert await view.ask(1, "Review [this](draft.md)", attachments=[item("draft.md")]) == "just text"
    await session.close()
    question = view.context()[0]
    assert (question.to, names(question.attachments)) == (1, ["draft.md"])


async def test_ask_with_a_missing_target_raises_and_posts_nothing():
    session, view = await driven(connectors=[_Plain()])
    with pytest.raises(ValueError, match="draft.md"):
        await view.ask(1, "Review [this](draft.md)")
    await session.close()
    assert view.context() == []


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
    assert view.context()[-1].attachments == ()


async def test_an_answer_linking_nothing_posts_nothing_and_the_chat_goes_on():
    session, view = await driven(connectors=[_Forgetful(), _Plain()])
    asyncio.create_task(view.ask(1, "?"))       # never answered: the reply was rejected
    await asyncio.sleep(0.05)
    assert await view.ask(2, "still there?") == "just text"
    await session.close()
    assert [m.frm for m in view.context()] == [LOCAL, LOCAL, 2]


async def test_a_command_result_can_attach_and_invoke_returns_its_text():
    session, view = await driven(commands=[_Export()])
    assert await view.command("exporta") == "[export](data.csv)"
    await session.close()
    invocation, result = view.context()
    assert invocation.attachments == ()
    assert (result.frm, names(result.attachments)) == (TOOL, ["data.csv"])


async def test_a_command_result_linking_nothing_raises_from_invoke():
    session, view = await driven(commands=[_Broken()])
    with pytest.raises(ValueError, match="data.csv"):
        await view.command("quebrado")
    await session.close()
    assert [m.text for m in view.context()] == ["/quebrado"]
