"""Tests for the A2A request payload.

Correlation is what routes an answer back to the right exchange, so where
taskId and contextId sit in the payload is load-bearing, not cosmetic.
"""

from unittest.mock import MagicMock

from chatinho import A2AConnector


def sent_payload(**kwargs) -> dict:
    """Runs ask() against a stubbed session and returns the JSON it posted."""
    connector = A2AConnector(name="a2a", url="https://agent.example", api_key="k")
    connector.session = MagicMock()
    connector.session.post.return_value = MagicMock(
        status_code=200, json=lambda: {"ok": True}, raise_for_status=lambda: None
    )
    connector.ask("ola", **kwargs)
    return connector.session.post.call_args.kwargs["json"]


def test_the_message_carries_the_text_and_role():
    payload = sent_payload()
    assert payload["message"]["role"] == "user"
    assert payload["message"]["parts"][0]["text"] == "ola"


def test_context_id_travels_inside_the_message():
    assert sent_payload(context_id="ctx-1")["message"]["contextId"] == "ctx-1"


def test_task_id_travels_inside_the_message_beside_context_id():
    """It used to sit at the top level, where the agent never saw it."""
    payload = sent_payload(task_id="task-1")
    assert payload["message"]["taskId"] == "task-1"
    assert "taskId" not in payload


def test_both_correlation_ids_sit_together():
    message = sent_payload(context_id="ctx-1", task_id="task-1")["message"]
    assert (message["contextId"], message["taskId"]) == ("ctx-1", "task-1")


def test_no_correlation_keys_when_none_were_given():
    message = sent_payload()["message"]
    assert "taskId" not in message
    assert "contextId" not in message
