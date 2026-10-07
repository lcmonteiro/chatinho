"""What crosses an MCP link: what McpFrontend writes is what McpConnector reads back."""

import pytest

from chatinho import Attachment
from chatinho.connectors import mcp as connector
from chatinho.frontends import mcp as frontend


def test_a_result_reads_back_as_written():
    chart = Attachment("chart.svg", "image/svg+xml", b"<svg/>")
    res   = frontend._result("answered", "here [chart](chart.svg)", [chart], "msg-0123456789abcdef")
    got   = connector._read_result(res)
    assert (got.status, got.msg_id) == ("answered", "msg-0123456789abcdef")
    assert got.text == "here [chart](chart.svg)"
    assert got.attachments == (chart,)
    assert not res.is_error


@pytest.mark.parametrize("status", ["error", "timeout"])
def test_errors_and_timeouts_are_tool_errors(status):
    res = frontend._result(status, "what went wrong")
    assert res.is_error
    assert res.content[0].text == "[%s] what went wrong" % status


def test_an_unknown_status_is_refused():
    with pytest.raises(ValueError):
        frontend._result("maybe", "x")


def test_a_plain_result_is_answered_or_an_error():
    import mcp_types as types
    plain = types.CallToolResult(content=[types.TextContent(text="hi")])
    assert connector._read_result(plain).status == "answered"
    failed = types.CallToolResult(content=[types.TextContent(text="no")], is_error=True)
    assert connector._read_result(failed) == connector._Remote("error", "no")


@pytest.mark.parametrize("raw, name", [
    ("lab", "lab"), ("a/b", "a-b"), ("  two  words ", "two words"),
    ("", "client"), (None, "client"), (3, "client"),
])
def test_names_are_safe_for_a_peer_path(raw, name):
    assert frontend._safe_name(raw, "client") == name
    assert connector._safe_name(raw, "client") == name


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
    assert frontend._media_type_of("chart.svg") == "image/svg+xml"
    assert frontend._media_type_of("blob") == "application/octet-stream"


def test_both_ends_agree_on_the_contract():
    assert frontend.CREDENTIALS_KEY == connector.CREDENTIALS_KEY
    assert frontend.STATUSES == connector.STATUSES
    assert frontend.DEFAULT_DEADLINE == connector.DEFAULT_DEADLINE
