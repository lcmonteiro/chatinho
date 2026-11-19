"""
Tests for the viewer page: served by the hive, self-contained, and drawing a message's traces.

The browser test runs only where Playwright and its Chromium can be used.
"""

import re
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from chatinho import ChatTrace, TraceID, TraceState
from chatinho.hive import create_app
from chatinho.support.parts.hive import KEY_HEADER, trace_to_wire
from fakes.hive import make_hive, message, served, wire_messages


# @ac AC-HIVE-008.1
def test_the_page_is_served_without_a_key_and_loads_nothing_from_elsewhere(tmp_path):
    hive = make_hive(tmp_path)
    with TestClient(create_app(hive.db)) as client:
        page = client.get("/")
    assert page.status_code == 200
    assert page.headers["content-type"].startswith("text/html")
    html = page.text
    assert "<html" in html.lower()
    assert 'name="viewport"' in html
    # Every src= and href= is on the hive itself: relative, or a fragment.
    for url in re.findall(r'(?:src|href)\s*=\s*["\']([^"\']+)', html):
        assert not re.match(r"^(?:[a-z]+:)?//", url, re.I), url
    assert "@import" not in html


def _browser():
    playwright = pytest.importorskip("playwright.sync_api")
    manager = playwright.sync_playwright().start()
    try:
        browser = manager.chromium.launch()
    except Exception as exc:                                          # no browser on this machine
        # Stop it, or its event loop outlives the test and every later one trips on it.
        manager.stop()
        pytest.skip("no browser: %s" % exc)
    return manager, browser


# @ac AC-HIVE-008.2
def test_the_page_lists_shows_and_draws_the_traces(tmp_path):
    hive = make_hive(tmp_path, "team")
    msg  = message(1, "summarise the repo")
    root = ChatTrace(id=TraceID.new(), msg_id=msg.id, state=TraceState.RUNNING, text="extract", frm=1,
                     timestamp=msg.timestamp + timedelta(seconds=1))
    leaf = ChatTrace(id=TraceID.new(), msg_id=msg.id, state=TraceState.DONE, text="tool ws_ls", frm=1,
                     prev=root.id, timestamp=msg.timestamp + timedelta(seconds=2))
    with TestClient(create_app(hive.db)) as client:
        key = {KEY_HEADER: hive.keys["team"]}
        client.post("/api/messages", json={"messages": wire_messages(msg)}, headers=key)
        client.post("/api/traces", json={"traces": [trace_to_wire(t, "dev") for t in (root, leaf)]},
                    headers=key)
    manager, browser = _browser()
    try:
        with served(hive.db) as server:
            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.goto(server.url + "/")
            page.get_by_test_id("key").fill(hive.admin)
            page.get_by_test_id("key-save").click()
            page.get_by_test_id("chat").filter(has_text="team").click()
            page.get_by_test_id("message").filter(has_text="summarise the repo").click()
            graph = page.get_by_test_id("graph")
            graph.get_by_text("extract").wait_for(timeout=5000)
            graph.get_by_text("tool ws_ls").wait_for(timeout=5000)
            assert graph.locator("[data-testid=edge]").count() == 1
            edge = graph.locator("[data-testid=edge]").first
            assert edge.get_attribute("data-from") == str(root.id)
            assert edge.get_attribute("data-to") == str(leaf.id)
    finally:
        browser.close()
        manager.stop()
