"""
An agent sees the files its question came with.

The files go to a real backend (``DatabaseBackend``, which links them as
``file://``) or to one of the test's own that answers with a plain path, as
``HiveBackend`` does; the model is scripted (``fakes.agent``).
"""

from typing import Dict, List, Optional, Tuple

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage

from chatinho import Attachment, BasicAgentConnector, DatabaseBackend, HookKeep, HookLink, MessageID
from chatinho import backend, require
from chatinho.support.kits.agent.attachments import ATTACHMENT_SHOWN
from chatinho.support.parts.attachments import linked_names, read_link

from conftest import driven
from fakes.agent import fake, question, says, this_run


@backend("files")
@require(HookKeep)
@require(HookLink)
class PathBackend:
    """Keeps attachments in memory and links each as a plain local path, as HiveBackend does."""

    def __init__(self, folder) -> None:
        self.folder = folder
        self.kept   : Dict[Tuple[str, str], bytes] = {}

    async def keep(self, msg_id: MessageID, attachments) -> None:
        for item in attachments:
            self.kept[(str(msg_id), item.name)] = item.data

    async def link(self, msg_id: MessageID, name: str) -> Optional[str]:
        data = self.kept.get((str(msg_id), name))
        if data is None:
            return None
        path = self.folder / ("%s-%s" % (msg_id.hex, name))
        path.write_bytes(data)
        return str(path)


def _sent(model) -> List[BaseMessage]:
    return model.sent[-1]


# @ac AC-AGENT-014.1
async def test_a_text_file_is_in_the_question():
    model = fake(says("It has two rows."))
    agent = BasicAgentConnector("analyst", model)
    session, view = await driven(connectors=[agent], backend=DatabaseBackend("sqlite:///:memory:"))
    csv   = Attachment("data.csv", "text/csv", b"a,b\n1,2\n3,4\n")
    reply = await view.ask(agent.peer_id, "How many rows has [the data](data.csv)?", attachments=[csv])
    await session.close()
    assert reply.text == "It has two rows."
    shown = question(_sent(model))
    assert shown.startswith("How many rows has [the data](data.csv)?")
    assert '<attachment name="data.csv" type="text/csv">\na,b\n1,2\n3,4\n</attachment>' in shown


# @ac AC-AGENT-014.2
async def test_a_plain_path_is_read_too(tmp_path):
    model = fake(says("ok"))
    agent = BasicAgentConnector("analyst", model)
    session, view = await driven(connectors=[agent], backend=PathBackend(tmp_path))
    await view.ask(agent.peer_id, "Read [notes](notes.md).",
                   attachments=[Attachment("notes.md", "text/markdown", b"# Plan\n")])
    await session.close()
    assert "# Plan" in question(_sent(model))


# @ac AC-AGENT-014.3
async def test_a_file_that_is_not_text_is_named():
    model = fake(says("A picture."))
    agent = BasicAgentConnector("analyst", model)
    session, view = await driven(connectors=[agent], backend=DatabaseBackend("sqlite:///:memory:"))
    png   = b"\x89PNG\r\n\x1a\n\x00\x00\xff\xfe"
    await view.ask(agent.peer_id, "What is [this](chart.png)?",
                   attachments=[Attachment("chart.png", "image/png", png)])
    await session.close()
    shown = question(_sent(model))
    assert '<attachment name="chart.png" type="image/png" bytes="%d">not text' % len(png) in shown
    assert "PNG" not in shown


# @ac AC-AGENT-014.4
async def test_no_file_no_tool_and_the_question_as_it_was():
    model = fake(says("ok"))
    agent = BasicAgentConnector("analyst", model)
    session, view = await driven(connectors=[agent], backend=DatabaseBackend("sqlite:///:memory:"))
    await view.ask(agent.peer_id, "See [missing](gone.txt) and [the docs](https://example.org/a.txt).")
    await session.close()
    assert question(_sent(model)) == "See [missing](gone.txt) and [the docs](https://example.org/a.txt)."
    assert not any("read_attachment" in bound for bound in model.tools)


def _reads(**args):
    """A script that calls read_attachment with *args* once a run, then answers with what it read."""
    def script(messages: List[BaseMessage]) -> AIMessage:
        results = [m for m in this_run(messages) if isinstance(m, ToolMessage)]
        if not results:
            return AIMessage(content="", tool_calls=[{"name": "read_attachment", "args": args, "id": "r1"}])
        return AIMessage(content=str(results[-1].content))
    return script


# @ac AC-AGENT-014.5
async def test_a_long_file_is_cut_and_read_on():
    lines = ["line %05d %s\n" % (n, "x" * 80) for n in range(1, 1001)]
    big   = "".join(lines).encode()
    kept  = ATTACHMENT_SHOWN // len(lines[0])
    model = fake(_reads(name="log.txt", start=kept + 1, count=2))
    agent = BasicAgentConnector("analyst", model)
    session, view = await driven(connectors=[agent], backend=DatabaseBackend("sqlite:///:memory:"))
    reply = await view.ask(agent.peer_id, "Summarise [the log](log.txt).",
                           attachments=[Attachment("log.txt", "text/plain", big)])
    await session.close()
    shown = question(model.sent[0])
    assert len(shown) < ATTACHMENT_SHOWN + 500
    assert "[cut after line %d of 1000; read on with read_attachment(name='log.txt', start=%d)]" \
        % (kept, kept + 1) in shown
    assert "read_attachment" in model.tools[-1]
    assert reply.text == "[log.txt, lines %d-%d of 1000, more follow]\n%s" % (
        kept + 1, kept + 2, "".join(lines[kept:kept + 2]))


# @ac AC-AGENT-014.6
async def test_a_remembered_file_can_be_read_again():
    model = fake(says("noted"))
    agent = BasicAgentConnector("analyst", model)
    session, view = await driven(connectors=[agent], backend=DatabaseBackend("sqlite:///:memory:"))
    await view.ask(agent.peer_id, "Keep [the plan](plan.md).",
                   attachments=[Attachment("plan.md", "text/markdown", b"step one\nstep two\n")])
    model.script = _reads(name="plan.md", start=2)
    reply = await view.ask(agent.peer_id, "What is the plan's second line?")
    model.script = _reads(name="other.md")
    missing = await view.ask(agent.peer_id, "And other.md?")
    await session.close()
    assert reply.text == "[plan.md, lines 2-2 of 2]\nstep two\n"
    assert missing.text == "no attached file is called 'other.md'"


# @ac AC-AGENT-014.7
def test_reading_links(tmp_path):
    path = tmp_path / "a.txt"
    path.write_bytes(b"hi")
    assert read_link(path.as_uri()) == b"hi"
    assert read_link(str(path)) == b"hi"
    assert read_link("https://example.org/a.txt") is None
    assert read_link("a.txt") is None
    assert read_link(str(tmp_path / "missing")) is None
    assert read_link(None) is None
    assert linked_names("[a](a.txt) [b](<my%20b.md>) [c](https://x.org/c) [a](a.txt) [d](#d)") == \
        ["a.txt", "my b.md"]
