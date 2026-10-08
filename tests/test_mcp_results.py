"""What crosses an MCP link: what McpFrontend writes is what McpConnector reads back."""

import mcp_types as types

from chatinho import Attachment, Reply, ReplyStatus
from chatinho.connectors import mcp as connector
from chatinho.frontends import mcp as frontend
from chatinho.helpers import mcp as helpers


def _sent(answer):
    """What a client receives for *answer*."""
    return types.CallToolResult(content=[types.TextContent(text=answer.text)],
                                structured_content=answer.model_dump(mode="json"))


def test_an_answer_becomes_the_reply_with_its_attachments():
    chart = Attachment("chart.svg", "image/svg+xml", b"<svg/>")
    sent  = _sent(frontend.Answer(status=ReplyStatus.ANSWERED, text="here [chart](chart.svg)",
                                  attachments=[helpers.encode(chart)], msg_id="msg-0123456789abcdef"))
    assert connector._reply_from(sent, "lab") == Reply("here [chart](chart.svg)", (chart,))


def test_a_question_back_is_marked_asked():
    got = connector._reply_from(_sent(frontend.Answer(status=ReplyStatus.ASKED, text="which city?")), "lab")
    assert got == Reply("lab asks: which city?", status=ReplyStatus.ASKED)


def test_a_plain_result_is_answered_or_an_error():
    plain = types.CallToolResult(content=[types.TextContent(text="hi")])
    assert connector._reply_from(plain, "lab") == Reply("hi")
    failed = types.CallToolResult(content=[types.TextContent(text="no")], is_error=True)
    assert connector._reply_from(failed, "lab") == Reply("lab: error — no", status=ReplyStatus.ERROR)


def test_attachments_are_the_relative_links():
    text = ("[a](chart.svg) [b](https://x.org/y.png) [c](/abs.png) [d](#top) "
            "[e](chart.svg) [f](<my%20file.html>)")
    assert frontend._linked_names(text) == ["chart.svg", "my file.html"]


def test_only_file_links_are_read(tmp_path):
    path = tmp_path / "chart.svg"
    path.write_bytes(b"<svg/>")
    assert frontend._read_link(path.as_uri()) == b"<svg/>"
    assert frontend._read_link("https://example.org/chart.svg") is None
    assert frontend._read_link((tmp_path / "missing").as_uri()) is None
    assert frontend._read_link(None) is None


def test_media_types():
    assert helpers.media_type_of("chart.svg") == "image/svg+xml"
    assert helpers.media_type_of("blob") == "application/octet-stream"


def test_an_attachment_survives_the_trip():
    chart = Attachment("chart.svg", "image/svg+xml", b"<svg/>")
    assert helpers.decode(helpers.encode(chart)) == chart
